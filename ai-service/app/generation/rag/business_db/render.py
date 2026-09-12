"""The single renderer for the business-db block.

What is measured is what is sent, same reason as `render_hit_block`. The drop
order is declared: dependency tables from the tail of the coverage order, then
rows from the tail, then column descriptions, then the table description. The
window declaration is never trimmed, a row is never split in half, and a table
never loses the routines that justify it -- without them it stops being citable.

|| El único renderer del bloque de base. Lo que se mide es lo que se manda.
"""

from __future__ import annotations

from app.generation.rag.business_db.models import (
    DECLARED_TRUNCATION,
    INCOMPLETE_OUTCOMES,
    BusinessDbContext,
    CodeResolution,
    ResolutionOutcome,
)
from app.generation.rag.chunking.base import count_tokens

# Tables first, from the tail of the coverage-ordered list, so the least-covered
# go first and the best-covered survives. There is no role that is exempt: with
# no `core` to protect (see `roles.py`), coverage IS the protection, and it is
# two declared counts rather than a threshold.
# || Primero las tablas, desde la cola del orden por cobertura. Sin `core` que
# proteger, la cobertura ES la protección, y son dos conteos declarados.
DROP_ORDER = (
    "dependency_tables_tail",
    "rows_tail",
    "column_descriptions",
    "table_description",
)

_AUTHORITY = (
    "Este bloque NO es documentación funcional: es lo que la base del sistema "
    "declara hoy. Si difiere de la especificación, reportá la diferencia; no "
    "elijas una de las dos fuentes. No afirmes que un catálogo está completo "
    "cuando más abajo dice que quedó algo afuera."
)

_CAUSE_LINE: dict[ResolutionOutcome, str] = {
    "table_not_in_dictionary": "no está en el diccionario de la corrida",
    "table_not_loaded": "no tiene filas cargadas en esta corrida",
    "rows_capped": "tiene más filas que el tope configurado",
    "columns_unknown": "no tiene columnas extraídas (columns es NULL)",
    "date_unparsed": "tiene fechas que no se pudieron interpretar",
    "dropped_by_budget": "se recortó para entrar en el presupuesto de tokens",
    "not_in_run": "no aparece en WINDOWS de esta corrida",
    "no_maintained_table": "no declara tabla que mantenga",
    "ng_identi_ignored_by_type": "declara NG_IDENTI pero no es tipo 10; se ignora",
    "no_validity_mechanism": "no tiene mecanismo de vigencia declarado",
    "validity_discrepancy": "tiene filas donde estado y período discrepan",
    "resolved": "se resolvió",
    "edges_not_built": (
        "la corrida activa no tiene construidas las tablas por dependencia"
    ),
    "no_dependency_routine": "ninguna rutina de la base la nombra",
    "routine_without_tables": "sus rutinas no dependen de ninguna tabla",
    "code_too_short_to_anchor": "el código es demasiado corto para anclar (largo < 5)",
    "dependency_tables_capped": "toca más tablas que el tope configurado",
    "role_unknown": "hay tablas cuyo rol no se pudo derivar de una regla declarada",
}

_ROLE_LABEL = {
    "reference": "referencia",
    "historical": "histórica",
    "message": "mensajes",
    "validation": "validación",
    "unknown": "rol no declarado",
}


def render_block(context: BusinessDbContext, *, budget: int) -> BusinessDbContext:
    """Render the block into ``budget`` tokens and record what was dropped.

    Returns a copy of ``context`` with ``block_emitted``, ``tokens_used``,
    trimmed rows, and any `dropped_by_budget` causes. ``budget <= 0`` emits
    nothing and marks the drop: evidence and memory already used the ceiling.

    || Renderiza el bloque en ``budget`` tokens y registra lo recortado.
    """
    if context.absent_reason or not context.resolutions:
        return context.model_copy(update={"block_emitted": False, "tokens_used": 0})

    if budget <= 0:
        marked = [
            _with_cause(resolution, "dropped_by_budget")
            for resolution in context.resolutions
        ]
        return context.model_copy(
            update={
                "resolutions": marked,
                "block_emitted": False,
                "tokens_used": 0,
                "complete": False,
            }
        ).with_completeness()

    working = [resolution.model_copy(deep=True) for resolution in context.resolutions]
    include_columns = True
    include_table = True

    def _text() -> str:
        return _compose(context, working, include_columns, include_table)

    while (
        working
        and any(len(item.dependency_tables) > 1 for item in working)
        and count_tokens(_text()) > budget
    ):
        _drop_one_table(working)
    while working and any(item.rows for item in working) and count_tokens(_text()) > budget:
        _drop_one_row(working)
    if count_tokens(_text()) > budget:
        include_columns = False
        for item in working:
            item.dropped_column_descriptions = True
            if item.dictionary and item.dictionary.columns:
                _add_cause(item, "dropped_by_budget")
    if count_tokens(_text()) > budget:
        include_table = False
        for item in working:
            item.dropped_table_description = True
            if item.dictionary and (item.dictionary.description_es or item.dictionary.description_en):
                _add_cause(item, "dropped_by_budget")

    text = _text()
    used = count_tokens(text)
    # Window declarations stay even if they slightly exceed: they are the one
    # thing a RAG cannot reconstruct by similarity, same reason memory facts
    # are emitted over budget.
    # || Las declaraciones de ventana se conservan aunque se pasen un poco.
    return context.model_copy(
        update={
            "resolutions": working,
            "block_emitted": True,
            "tokens_used": used,
        }
    ).with_completeness()


def block_text(context: BusinessDbContext) -> str | None:
    """The text last rendered for ``context``, or ``None`` when there is no block.

    Re-renders from the (already trimmed) resolutions. Call after
    :func:`render_block`.

    || El texto ya recortado, o ``None`` cuando no hay bloque.
    """
    if not context.block_emitted or not context.resolutions:
        return None
    include_columns = not any(item.dropped_column_descriptions for item in context.resolutions)
    include_table = not any(item.dropped_table_description for item in context.resolutions)
    return _compose(context, context.resolutions, include_columns, include_table)


def _drop_one_table(resolutions: list[CodeResolution]) -> None:
    """Drop the lowest-coverage table of the resolution that has the most.

    Never below one: a code that kept nothing would read as "touches no tables",
    which is a different fact and already has its own cause. The dropped table
    is counted, so the section can say how many it is hiding.

    || Saca la tabla de menor cobertura de la resolución que más tenga. Nunca
    por debajo de una: un código sin ninguna se leería como «no toca tablas».
    """
    candidates = [item for item in resolutions if len(item.dependency_tables) > 1]
    if not candidates:
        return
    target = max(candidates, key=lambda item: len(item.dependency_tables))
    target.dependency_tables = target.dependency_tables[:-1]
    _add_cause(target, "dependency_tables_capped")


def _drop_one_row(resolutions: list[CodeResolution]) -> None:
    """Drop one whole row from the tail of the last resolution that still has one.

    || Saca una fila entera de la cola de la última resolución que todavía tenga.
    """
    for resolution in reversed(resolutions):
        if not resolution.rows:
            continue
        resolution.rows = resolution.rows[:-1]
        resolution.rows_shown = len(resolution.rows)
        _add_cause(resolution, "dropped_by_budget")
        return


def _add_cause(resolution: CodeResolution, cause: ResolutionOutcome) -> None:
    if cause not in resolution.causes:
        resolution.causes.append(cause)


def _with_cause(resolution: CodeResolution, cause: ResolutionOutcome) -> CodeResolution:
    copy = resolution.model_copy(deep=True)
    _add_cause(copy, cause)
    return copy


def _compose(
    context: BusinessDbContext,
    resolutions: list[CodeResolution],
    include_columns: bool,
    include_table: bool,
) -> str:
    run = context.run_id or "(sin corrida)"
    env = context.env or "(sin ambiente)"
    as_of = context.as_of.isoformat() if context.as_of else "(sin fecha de referencia)"
    lines = [
        "## Lo que declara la base (otra autoridad)",
        f"Corrida: {run} · ambiente: {env} · vigencia al: {as_of}",
        "",
        _AUTHORITY,
        "",
    ]
    for resolution in resolutions:
        lines.extend(_resolution_lines(resolution, include_columns, include_table))
        lines.append("")
    lines.extend(_completeness_lines(context, resolutions))
    return "\n".join(lines).rstrip() + "\n"


def _resolution_lines(
    resolution: CodeResolution,
    include_columns: bool,
    include_table: bool,
) -> list[str]:
    title = resolution.window_description or resolution.code
    kind = resolution.window_type_name or resolution.window_type or "sin tipo"
    status = resolution.window_status or "sin estado declarado"
    lines = [
        f"### {resolution.code} — {title}",
        f"Tipo de ventana: {kind}. Estado declarado: {status}.",
    ]
    if resolution.outcome == "not_in_run":
        lines.append("Este código no está en WINDOWS de la corrida.")
        lines.extend(_table_lines(resolution))
        return lines
    if resolution.outcome == "no_maintained_table":
        lines.append("La base no declara una tabla que esta transacción mantenga.")
        lines.extend(_table_lines(resolution))
        return lines
    if resolution.outcome == "ng_identi_ignored_by_type":
        lines.append(
            f"Declara NG_IDENTI={resolution.ng_identi} pero el tipo no es 10 "
            "(Tabla general); el valor se ignora."
        )
        lines.extend(_table_lines(resolution))
        return lines
    if resolution.table_name:
        lines.append(f"Tabla que mantiene: {resolution.table_name}.")
    if resolution.outcome == "table_not_in_dictionary":
        lines.append("Esa tabla no está en el diccionario de la corrida.")
        return lines
    if resolution.outcome == "table_not_loaded":
        lines.append("Esa tabla no tiene filas cargadas en `business_data` para esta corrida.")
        return lines

    dictionary = resolution.dictionary
    if include_table and dictionary:
        description = dictionary.description_es or dictionary.description_en
        if description:
            lines.append(f"Descripción de la tabla: {description}")
    if include_columns and dictionary and dictionary.columns:
        lines.append("Columnas:")
        for column in dictionary.columns:
            if column.description:
                lines.append(f"- {column.name}: {column.description}")
            else:
                lines.append(f"- {column.name}")
    elif dictionary and dictionary.columns is None:
        lines.append("Columnas: no extraídas (columns es NULL).")

    if resolution.mechanism == "none" or "no_validity_mechanism" in resolution.causes:
        lines.append(
            "Sin mecanismo de vigencia declarado: las filas no se filtraron."
        )
    if resolution.validity_discrepancy_count:
        lines.append(
            f"Discrepancia estado/período: {resolution.validity_discrepancy_count} "
            "filas, sin decidir cuál gana."
        )

    lines.extend(_table_lines(resolution))

    if resolution.rows:
        shown = resolution.rows_shown
        valid = resolution.rows_valid
        if shown < valid:
            lines.append(f"Filas vigentes: {valid}, se muestran {shown}.")
        else:
            lines.append(f"Filas vigentes: {valid}.")
        headers = _headers(resolution)
        if headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in resolution.rows:
                cells = [_cell(row.values, header) for header in headers]
                lines.append("| " + " | ".join(cells) + " |")
    return lines


def _table_lines(resolution: CodeResolution) -> list[str]:
    """The tables this transaction touches, with the routines that justify each.

    The routine list is never trimmed: without it the table stops being citable
    and becomes an assertion with no origin.

    || Las tablas que toca, con las rutinas que justifican cada una. La lista de
    rutinas no se recorta nunca.
    """
    if not resolution.dependency_tables:
        if "no_dependency_routine" in resolution.causes:
            return ["Ninguna rutina de la base nombra este código."]
        if "edges_not_built" in resolution.causes:
            return [
                (
                    "Las tablas por dependencia no están construidas para esta "
                    "corrida; no se sabe qué tablas toca."
                )
            ]
        return []
    shown = len(resolution.dependency_tables)
    total = resolution.dependency_tables_total
    header = (
        f"Tablas que toca (grafo de dependencias de Oracle): {total}"
        if shown >= total
        else f"Tablas que toca (grafo de dependencias de Oracle): {total}, se muestran {shown}"
    )
    lines = [
        (
            f"{header}. El orden es por cuántas rutinas de la transacción llegan "
            "a cada una; no es una jerarquía de importancia declarada."
        ),
    ]
    for table in resolution.dependency_tables:
        label = _ROLE_LABEL.get(table.role, table.role)
        via = ", ".join(table.via_routines)
        detail = f"{table.routine_hits}/{table.routine_total} rutinas"
        lines.append(f"- {table.table_name} [{label}] — {detail}; vía {via}.")
        if table.description:
            lines.append(f"  {table.description}")
    if any(table.role == "unknown" for table in resolution.dependency_tables):
        lines.append(
            "Un rol «no declarado» significa que ninguna regla lo derivó: la "
            "transacción toca la tabla, pero en qué carácter no está declarado. "
            "No lo supongas."
        )
    return lines


def _headers(resolution: CodeResolution) -> list[str]:
    if resolution.dictionary and resolution.dictionary.columns:
        return [column.name for column in resolution.dictionary.columns]
    keys: list[str] = []
    for row in resolution.rows:
        for key in row.values:
            if key not in keys:
                keys.append(key)
    return keys


def _cell(values: dict[str, str | None], header: str) -> str:
    for key, value in values.items():
        if key.upper() == header.upper():
            return "" if value is None else value.replace("|", "/")
    return ""


def _completeness_lines(
    context: BusinessDbContext, resolutions: list[CodeResolution]
) -> list[str]:
    lines = ["## Qué no se pudo traer"]
    named = False
    for resolution in resolutions:
        for cause in resolution.causes:
            # Declared truncations are named here too, so a reader scanning
            # this section does not have to re-read every table list to notice
            # a cap -- but they do NOT make the context incomplete: the section
            # above states the real count, and the amount is exact.
            # || Las truncaciones declaradas se nombran acá igual, pero NO
            # vuelven incompleto el contexto: arriba está el conteo real.
            if cause not in INCOMPLETE_OUTCOMES and cause not in DECLARED_TRUNCATION:
                continue
            target = resolution.table_name or resolution.code
            lines.append(f"- {target} ({resolution.code}): {_CAUSE_LINE[cause]} ({cause}).")
            named = True
    for code in context.dropped_codes:
        lines.append(
            f"- {code}: no se resolvió; el tope de códigos anclados lo dejó afuera "
            "(dropped_by_budget)."
        )
        named = True
    if not named:
        lines.append("Se trajo todo lo que la base declara para estos códigos.")
    return lines

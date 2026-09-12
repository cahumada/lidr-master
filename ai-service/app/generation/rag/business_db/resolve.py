"""Resolve anchored transaction codes against the active mirror run.

The anchor is a declared `document_id`, not an entity guess. `NG_IDENTI`
resolves to `TABLE<n>` only for window type 10; any other type is ignored
and counted.

|| Resuelve códigos anclados contra la corrida activa del mirror. El ancla
es un `document_id` declarado. `NG_IDENTI` solo vale para el tipo 10.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING

import structlog

from app.generation.rag.business_db.dependencies import MIN_ANCHOR_LENGTH
from app.generation.rag.business_db.models import (
    BusinessDbContext,
    CodeResolution,
    ResolutionOutcome,
    parse_as_of,
)
from app.generation.rag.business_db.reader import (
    read_catalog_rows,
    read_dependency_tables,
    read_run_created_at,
    read_table_dictionary,
    run_has_edges,
)
from app.generation.rag.business_db.validity import (
    STATUS_ACTIVE_EQUALS_ONE,
    apply_status_filter,
    apply_validity,
    column_description,
    declared_mechanism,
)
from app.generation.rag.navigation import GENERAL_TABLE_WINDOW_TYPE, NavigationTree

if TYPE_CHECKING:  # pragma: no cover - typing only
    # `schemas` imports `business_db.models`, so importing SearchHit at runtime
    # closes a cycle: anything that reaches `schemas` first (alembic's env.py
    # does, through `store.models`) fails on a partially initialised module.
    # || `schemas` importa `business_db.models`, así que importar SearchHit en
    # runtime cierra un ciclo: lo que llegue primero a `schemas` —el env.py de
    # alembic lo hace— falla sobre un módulo a medio inicializar.
    from app.generation.rag.schemas import SearchHit

log = structlog.get_logger()

# Window type 10 — "Tabla general". The only type whose NG_IDENTI means
# "this transaction maintains TABLE<n>". Domain §7.1: 440/529 type-10 pairs
# match (83%); 0/11 pairs of other types match.
# || Tipo 10. El único cuyo NG_IDENTI significa «esta transacción mantiene
# TABLE<n>».
_TYPE_10 = GENERAL_TABLE_WINDOW_TYPE


def anchored_codes(hits: Sequence[SearchHit], *, max_codes: int) -> tuple[list[str], list[str]]:
    """Unique `document_id`s that entered the prompt, then the ones the cap left out.

    A hit that never reached the prompt does not anchor anything: the block
    describes what the answer can cite.

    || `document_id` únicos que entraron al prompt, y los que el tope dejó
    afuera. Un hit que no llegó al prompt no ancla nada.
    """
    seen: list[str] = []
    for hit in hits:
        code = (hit.document_id or "").strip()
        if not code or code in seen:
            continue
        seen.append(code)
    return seen[:max_codes], seen[max_codes:]


def _causes(*outcomes: ResolutionOutcome) -> list[ResolutionOutcome]:
    ordered: list[ResolutionOutcome] = []
    for outcome in outcomes:
        if outcome not in ordered:
            ordered.append(outcome)
    return ordered


def _resolution(
    code: str,
    outcome: ResolutionOutcome,
    *extra: ResolutionOutcome,
    **fields,
) -> CodeResolution:
    causes = _causes(outcome, *extra)
    return CodeResolution(code=code, outcome=outcome, causes=causes, **fields)


def resolve_context(
    *,
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
    codes: Sequence[str],
    tree: NavigationTree | None,
    max_rows: int,
    as_of_override: str | None = None,
    schema: str = "visualtime",
    with_tables: bool = False,
    max_tables: int = 0,
) -> BusinessDbContext:
    """Resolve each anchored code against one run. Sync, like the tree.

    || Resuelve cada código anclado contra una corrida. Sincrónico, como el árbol.
    """
    as_of = _as_of(
        database_url, tenant, env, run_id, as_of_override, schema=schema
    )
    has_edges = run_has_edges(database_url, tenant, env, run_id) if with_tables else False
    resolutions: list[CodeResolution] = []
    for code in codes:
        resolution = _resolve_one(
            code,
            database_url=database_url,
            tenant=tenant,
            env=env,
            run_id=run_id,
            tree=tree,
            max_rows=max_rows,
            as_of=as_of,
            schema=schema,
        )
        if with_tables:
            # An independent path: NG_IDENTI answers "what does this window
            # maintain?" and the dependency graph answers "what does it touch?".
            # A code absent from WINDOWS can still have routines, so this runs
            # even for `not_in_run`.
            # || Camino independiente: NG_IDENTI responde qué mantiene la
            # ventana y el grafo qué toca. Corre incluso para `not_in_run`.
            resolution = _attach_tables(
                resolution,
                database_url=database_url,
                tenant=tenant,
                env=env,
                run_id=run_id,
                max_tables=max_tables,
                has_edges=has_edges,
            )
        resolutions.append(resolution)
    context = BusinessDbContext(
        run_id=run_id,
        env=env,
        as_of=as_of,
        resolutions=resolutions,
    ).with_completeness()
    for resolution in context.resolutions:
        log.info(
            "business_db_resolution",
            code=resolution.code,
            outcome=resolution.outcome,
            causes=resolution.causes,
            table_name=resolution.table_name,
            rows_valid=resolution.rows_valid,
            rows_shown=resolution.rows_shown,
            rows_fetched=resolution.rows_fetched,
            date_unparsed=resolution.date_unparsed_count,
            validity_discrepancy=resolution.validity_discrepancy_count,
            status_normalized_from_4=resolution.status_normalized_from_4,
            mechanism=resolution.mechanism,
            dependency_tables=len(resolution.dependency_tables),
            dependency_tables_total=resolution.dependency_tables_total,
            run_id=run_id,
            env=env,
        )
    return context


def _attach_tables(
    resolution: CodeResolution,
    *,
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
    max_tables: int,
    has_edges: bool,
) -> CodeResolution:
    """Add the dependency-graph tables, or the cause that says why there are none.

    Every branch ends in a named cause from the closed vocabulary. The order
    matters: `edges_not_built` is checked FIRST, because without the batch every
    other answer would be indistinguishable from "this code touches nothing".

    || Agrega las tablas del grafo, o la causa que dice por qué no hay. Cada
    rama termina en una causa nombrada. `edges_not_built` se chequea PRIMERO.
    """
    updated = resolution.model_copy(deep=True)
    if not has_edges:
        _add(updated, "edges_not_built")
        return _repick(updated)
    if len(resolution.code) < MIN_ANCHOR_LENGTH:
        _add(updated, "code_too_short_to_anchor")
        return _repick(updated)

    tables, total, routines = read_dependency_tables(
        database_url, tenant, env, run_id, resolution.code, max_tables
    )
    updated.dependency_tables = list(tables)
    updated.dependency_tables_total = total
    updated.dependency_routines = list(routines)
    if not total:
        # No edge at all: either no routine names this code, or its routines
        # depend on no table. The two are different facts and the read cannot
        # tell them apart, so the narrower one is not claimed.
        # || Sin ninguna arista. Las dos causas son hechos distintos y la
        # lectura no las distingue, así que no se afirma la más específica.
        _add(updated, "no_dependency_routine")
        return _repick(updated)
    if total > len(tables):
        _add(updated, "dependency_tables_capped")
    if any(table.role == "unknown" for table in tables):
        _add(updated, "role_unknown")
    return _repick(updated)


def _add(resolution: CodeResolution, cause: ResolutionOutcome) -> None:
    if cause not in resolution.causes:
        resolution.causes.append(cause)


def _repick(resolution: CodeResolution) -> CodeResolution:
    """Name an incompleteness as the outcome when one is present.

    The closed vocabulary is what a reader greps for, so the outcome field
    always carries the worst thing that happened.

    || Nombra una incompletitud como outcome cuando la hay.
    """
    from app.generation.rag.business_db.models import INCOMPLETE_OUTCOMES

    if resolution.outcome in INCOMPLETE_OUTCOMES:
        return resolution
    incomplete = [cause for cause in resolution.causes if cause in INCOMPLETE_OUTCOMES]
    if incomplete:
        resolution.outcome = incomplete[0]
    return resolution


def _as_of(
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
    override: str | None,
    *,
    schema: str,
) -> date | None:
    parsed = parse_as_of(override)
    if parsed is not None:
        return parsed
    created = read_run_created_at(database_url, tenant, env, run_id, schema=schema)
    return parse_as_of(created)


def _resolve_one(
    code: str,
    *,
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
    tree: NavigationTree | None,
    max_rows: int,
    as_of: date | None,
    schema: str,
) -> CodeResolution:
    if tree is None or code not in tree.codes_set():
        return _resolution(code, "not_in_run")

    window_type = tree.window_type(code)
    ident = tree.ng_identi(code)
    base = {
        "window_type": window_type,
        "window_type_name": tree.window_type_name(code),
        "window_status": tree.window_status(code),
        "window_description": tree.description_of(code),
        "ng_identi": ident,
    }

    if not ident:
        return _resolution(code, "no_maintained_table", **base)

    if window_type != _TYPE_10:
        return _resolution(code, "ng_identi_ignored_by_type", **base)

    table_name = f"TABLE{ident}"
    dictionary = read_table_dictionary(
        database_url, tenant, env, run_id, table_name, schema=schema
    )
    if dictionary is None:
        return _resolution(
            code, "table_not_in_dictionary", table_name=table_name, **base
        )

    mechanism = declared_mechanism(dictionary.columns)
    extra: list[ResolutionOutcome] = []
    apply_status = True
    if mechanism == "unknown":
        extra.append("columns_unknown")
        apply_status = False
        effective_mechanism = "none"
    elif mechanism == "none":
        extra.append("no_validity_mechanism")
        apply_status = False
        effective_mechanism = "none"
    else:
        effective_mechanism = mechanism
        if mechanism in ("status", "both"):
            # STATUS_ACTIVE_EQUALS_ONE lives here so the comparison is never
            # a bare `"1"` with the evidence left implicit.
            # || El supuesto vive acá para que la comparación nunca sea un
            # `"1"` pelado con la evidencia implícita.
            _ = STATUS_ACTIVE_EQUALS_ONE
            description = column_description(dictionary.columns, "SSTATREGT")
            if not apply_status_filter(description):
                extra.append("no_validity_mechanism")
                apply_status = False
                if mechanism == "status":
                    effective_mechanism = "none"

    fetched, capped = read_catalog_rows(
        database_url, tenant, env, run_id, table_name, max_rows, schema=schema
    )
    if not fetched:
        return _resolution(
            code,
            "table_not_loaded",
            *extra,
            table_name=table_name,
            dictionary=dictionary,
            mechanism=None if mechanism == "unknown" else mechanism,
            **base,
        )

    if capped:
        extra.append("rows_capped")

    if as_of is None:
        # No date from the run and no override: do not invent now().
        # Period tables then have no predicate; we say so.
        # || Sin fecha de la corrida ni override: no se inventa now().
        counts_kept = list(fetched)
        date_unparsed = 0
        discrepancy = 0
        from_four = 0
        if effective_mechanism in ("period", "both"):
            extra.append("no_validity_mechanism")
    else:
        counts = apply_validity(
            list(fetched),
            mechanism=effective_mechanism,
            as_of=as_of,
            apply_status=apply_status,
        )
        counts_kept = counts.kept
        date_unparsed = counts.date_unparsed
        discrepancy = counts.validity_discrepancy
        from_four = counts.status_normalized_from_4

    if date_unparsed:
        extra.append("date_unparsed")
    if discrepancy:
        extra.append("validity_discrepancy")

    primary: ResolutionOutcome = "resolved"
    if extra:
        # Prefer an incompleteness as the named outcome when one is present,
        # so the closed vocabulary stays the thing a reader greps for.
        # || Si hay incompletitud, esa es la que se nombra.
        from app.generation.rag.business_db.models import INCOMPLETE_OUTCOMES

        incomplete = [cause for cause in extra if cause in INCOMPLETE_OUTCOMES]
        if incomplete:
            primary = incomplete[0]
    return _resolution(
        code,
        primary,
        *extra,
        table_name=table_name,
        dictionary=dictionary,
        rows=counts_kept,
        rows_valid=len(counts_kept),
        rows_shown=len(counts_kept),
        rows_fetched=len(fetched),
        mechanism=None if mechanism == "unknown" else mechanism,
        status_normalized_from_4=from_four,
        date_unparsed_count=date_unparsed,
        validity_discrepancy_count=discrepancy,
        **base,
    )

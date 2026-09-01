"""Text normalization for functional-spec markdown documents.

Two independent concerns live here: line-ending normalization (source files
are Windows exports, ``\\r\\n``) and repair of a recurring export bug where a
2-column table lost its ``| --- | --- |`` separator row and had its column
headers exported as ``####`` headings instead of a table header row.

Four broken shapes show up in the real corpus, all handled by
:func:`repair_broken_tables`:

* **Simple** — two ``####`` headers, then every data row on its own
  ``label |  value`` line (CA014 "Ramos generales / Vida", CA001 "Tipo de
  registro / Transacción" x2).
* **Paired** — two ``####`` headers, then each row's label repeated as its
  own ``####`` heading followed by a ``|  value`` line with no left cell
  (CA001 "Tipo de inicio de vigencia / Fecha a mostrar", 5 rows).
* **Split rows** — N headers, then rows spanning several lines: a line with
  no leading pipe starts a row, one with a leading pipe continues it.
* **Unpiped** — N non-italic ``####`` headers are the columns, then each
  row is an italic ``####`` label followed by plain prose, with no pipe
  anywhere (`cp001.md` "Título / Descripción", 407 files). A row label is
  italic and a column header is not: that is what separates the two in a run
  of consecutive ``####``, and what keeps a group divider such as
  ``_Parte repetitiva_`` from being read as a third column.

All four are reconstructed into a single, valid markdown table. A block whose
rows do not line up with its columns is NOT repaired: padding a short row at
the end would put a value under the wrong header, and a row repaired wrong is
worse than a row left broken. Those are logged instead.

|| Normalización de texto para los documentos markdown de especificación
funcional. Aquí viven dos responsabilidades independientes: normalización de
fin de línea (los archivos fuente son exports de Windows, ``\\r\\n``) y la
reparación de un bug de exportación recurrente donde una tabla de 2 columnas
perdió su fila separadora ``| --- | --- |`` y sus encabezados de columna
quedaron exportados como headings ``####`` en vez de fila de tabla.

Aparecen cuatro formas rotas en el corpus real, todas manejadas por
:func:`repair_broken_tables`:

* **Simple** — dos headers ``####``, luego cada fila de datos en su propia
  línea ``etiqueta |  valor`` (CA014 "Ramos generales / Vida", CA001 "Tipo
  de registro / Transacción" x2).
* **Pareada** — dos headers ``####``, luego la etiqueta de cada fila
  repetida como su propio heading ``####`` seguido de una línea
  ``|  valor`` sin celda izquierda (CA001 "Tipo de inicio de vigencia /
  Fecha a mostrar", 5 filas).
* **Filas partidas** — N headers, luego filas que abarcan varias líneas: una
  línea sin pipe inicial empieza una fila, una con pipe inicial la continúa.
* **Sin pipes** — N headers ``####`` no itálicos son las columnas, y cada
  fila es una etiqueta ``####`` itálica seguida de prosa pelada, sin ningún
  pipe (`cp001.md` "Título / Descripción", 407 archivos). Una etiqueta de
  fila es itálica y un encabezado de columna no: eso es lo que los separa en
  una corrida de ``####`` consecutivos, y lo que evita leer un divisor de
  grupo como ``_Parte repetitiva_`` como si fuera una tercera columna.

Las cuatro se reconstruyen en una única tabla markdown válida. Un bloque cuyas
filas no se alinean con sus columnas NO se repara: rellenar una fila corta al
final pondría un valor bajo el encabezado equivocado, y una fila mal reparada
es peor que una fila rota. Esos casos se registran en el log.
"""

from __future__ import annotations

import re

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger()

HEADER_LINE = re.compile(r"^####\s+(.*\S)\s*$")
SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")

# The unpiped shape also appears inside blockquotes: the export writes a nested
# row as ``> ####  _1.1 Especificaciones incorrectas_``. Only the unpiped pass
# uses this looser header; the three piped shapes keep ``HEADER_LINE``.
# || La forma sin pipes también aparece adentro de blockquotes: el export
# escribe una fila anidada como ``> ####  _1.1 Especificaciones incorrectas_``.
# Solo la pasada sin pipes usa este header más laxo; las tres formas con pipes
# siguen con ``HEADER_LINE``.
QUOTED_HEADER_LINE = re.compile(r"^\s*(?:>\s*)*####\s+(.*\S)\s*$")

# A row label is written in italics, a column header is not. That is what tells
# the two apart in a run of consecutive ``####``: in `cp001.md` the run is
# ``Título`` / ``Descripción`` / ``_Moneda_``, which is two columns and the
# first row's label — not three columns. The same marker separates a group
# divider (``_Parte repetitiva_``) from a real column.
# || Una etiqueta de fila se escribe en itálica, un encabezado de columna no.
# Eso es lo que los distingue en una corrida de ``####`` consecutivos: en
# `cp001.md` la corrida es ``Título`` / ``Descripción`` / ``_Moneda_``, que son
# dos columnas y la etiqueta de la primera fila — no tres columnas.
ITALIC_LABEL = re.compile(r"^(_.*_|__.*__|\*_.*_\*)$")

_LineKind = str  # "header" | "data" | "blank" | "other"


class RepairedTable(BaseModel):
    """One broken-table block reconstructed into valid markdown.

    Kept as a separate, traceable record (raw block + result) rather than
    silently overwriting the source, since these are insurance business
    rules — losing a cell without a trace would be dangerous.

    || Un bloque de tabla rota reconstruido en markdown válido. Se guarda
    como un registro separado y trazable (bloque crudo + resultado) en vez
    de sobrescribir la fuente en silencio, ya que son reglas de negocio de
    seguros — perder una celda sin dejar rastro sería peligroso.
    """

    raw_original: str = Field(
        description="The original, broken block — kept for traceability. "
        "|| El bloque original, roto — se conserva para trazabilidad."
    )
    repaired_markdown: str = Field(
        description="The reconstructed, valid markdown table. || La tabla markdown reconstruida y válida."
    )
    headers: list[str]
    warnings: list[str] = Field(default_factory=list)


def normalize_line_endings(text: str) -> str:
    """Normalize Windows line endings to ``\\n`` before any parsing.

    || Normaliza los fines de línea de Windows a ``\\n`` antes de cualquier parseo.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _strip_emphasis(text: str) -> str:
    """Strip surrounding markdown emphasis markers (``**bold**``, ``_italic_``).

    || Quita los marcadores de énfasis de markdown alrededor del texto (``**negrita**``, ``_itálica_``).
    """
    text = text.strip()
    text = re.sub(r"^[*_]+|[*_]+$", "", text)
    return text.strip()


def _classify_line(line: str) -> _LineKind:
    if line.strip() == "":
        return "blank"
    if HEADER_LINE.match(line):
        return "header"
    if "|" in line and not SEPARATOR_ROW.match(line):
        return "data"
    return "other"


def _is_row_start(lines: list[str], kinds: list[_LineKind], index: int) -> bool:
    """True for a pipe-less line that is a row's FIRST CELL, sitting alone.

    The third broken shape splits one row across lines: the first cell has no
    pipe at all and the rest continue with a leading ``|``. Distinguishing that
    from ordinary prose under a real ``####`` heading needs a tight test — the
    line must be IMMEDIATELY followed by one that starts with ``|``. Prose is
    not.

    || True para una línea sin pipe que es la PRIMERA CELDA de una fila, sola.
    La tercera forma rota parte una fila en varias líneas: la primera celda no
    tiene ningún pipe y el resto continúa con un ``|`` inicial. Distinguir eso
    de prosa normal bajo un ``####`` real exige una prueba tensa — la línea
    debe estar seguida INMEDIATAMENTE por una que empiece con ``|``. La prosa no.
    """
    if kinds[index] != "other":
        return False
    for next_index in range(index + 1, len(lines)):
        if kinds[next_index] == "blank":
            continue
        return lines[next_index].lstrip().startswith("|")
    return False


def _opens_a_table_body(lines: list[str], kinds: list[_LineKind], index: int) -> bool:
    """Whether a table body starts at ``index``: a pipe row, or a split row.

    || Si un cuerpo de tabla empieza en ``index``: una fila con pipes, o una
    fila partida en varias líneas.
    """
    return kinds[index] == "data" or _is_row_start(lines, kinds, index)


def _find_candidate_blocks(lines: list[str], kinds: list[_LineKind]) -> list[tuple[int, int]]:
    """Find maximal runs that look like a broken table export.

    A run only qualifies when it opens with >=2 consecutive ``####`` headers
    (blank lines allowed between them) immediately followed by a pipe-bearing
    data line — a lone ``####`` followed by ordinary prose never matches, so
    a real heading is left untouched.

    || Encuentra las corridas maximales que parecen una tabla exportada
    rota. Una corrida solo califica cuando abre con >=2 headers ``####``
    consecutivos (se permiten líneas en blanco entre ellos) seguidos
    inmediatamente por una línea de datos con "|" — un ``####`` suelto
    seguido de prosa normal nunca matchea, así que un heading real queda
    intacto.
    """
    blocks: list[tuple[int, int]] = []
    i = 0
    n = len(lines)
    while i < n:
        if kinds[i] == "header":
            j = i
            header_run = 0
            while j < n and kinds[j] in ("header", "blank"):
                if kinds[j] == "header":
                    header_run += 1
                j += 1
            if header_run >= 2 and j < n and _opens_a_table_body(lines, kinds, j):
                k = j
                while k < n and (
                    kinds[k] in ("header", "data", "blank")
                    or _is_row_start(lines, kinds, k)
                ):
                    k += 1
                while k > j and kinds[k - 1] == "blank":
                    k -= 1
                blocks.append((i, k))
                i = k
                continue
        i += 1
    return blocks


def _parse_block(block_lines: list[str]) -> tuple[list[str], list[list[str]], list[str]] | None:
    """Interpret one candidate block as one of the 2 broken-table shapes, or bail out.

    || Interpreta un bloque candidato como una de las 2 formas de tabla rota, o desiste.
    """
    tokens: list[tuple[_LineKind, str]] = []
    for line in block_lines:
        kind = _classify_line(line)
        if kind == "blank":
            continue
        tokens.append((kind, line))
    if len(tokens) < 3:
        return None

    def header_text(line: str) -> str:
        match = HEADER_LINE.match(line)
        assert match is not None
        return _strip_emphasis(match.group(1))

    warnings: list[str] = []

    leading = 0
    while leading < len(tokens) and tokens[leading][0] == "header":
        leading += 1
    tail = tokens[leading:]

    # Shape 1 (simple): N leading headers, then every remaining line is data.
    # || Forma 1 (simple): N headers al inicio, luego todo el resto son líneas de datos.
    if tail and all(kind == "data" for kind, _ in tail):
        headers = [header_text(line) for _, line in tokens[:leading]]
        rows: list[list[str]] = []
        for _, line in tail:
            cells = [c.strip() for c in line.split("|", len(headers) - 1)]
            if len(cells) < len(headers):
                warnings.append(
                    f"row '{line.strip()}' has {len(cells)} cell(s), expected "
                    f"{len(headers)}; padded with \"\""
                )
                cells = cells + [""] * (len(headers) - len(cells))
            rows.append(cells[: len(headers)])
        return headers, rows, warnings

    # Shape 2 (paired): first 2 headers are the true columns; each subsequent
    # header is a row label, followed by a "|value" data line for that row.
    # || Forma 2 (pareada): los primeros 2 headers son las columnas reales;
    # cada header siguiente es la etiqueta de una fila, seguida de una línea
    # de datos "|valor" para esa fila.
    # The paired shape is recognised by its ALTERNATION: after the two real
    # column headers, every row label is itself a `####`. A block whose leading
    # headers are all consecutive and whose tail has none is shape 1 or 3
    # instead — without this guard, a 5-column split-row table was read as a
    # 2-column paired one, turning three of its column headers into rows.
    # || La forma pareada se reconoce por su ALTERNANCIA: después de los dos
    # headers de columna reales, cada etiqueta de fila es a su vez un `####`.
    # Un bloque cuyos headers iniciales son todos consecutivos y cuya cola no
    # tiene ninguno es forma 1 o 3 — sin esta guarda, una tabla de 5 columnas
    # con filas partidas se leía como una pareada de 2, convirtiendo tres de sus
    # headers de columna en filas.
    tail_has_headers = any(kind == "header" for kind, _line in tail)
    if tail_has_headers and tokens[0][0] == "header" and tokens[1][0] == "header":
        rest = tokens[2:]
        if rest and rest[0][0] == "header":
            headers = [header_text(tokens[0][1]), header_text(tokens[1][1])]
            rows = []
            idx = 0
            while idx < len(rest):
                kind, line = rest[idx]
                if kind != "header":
                    idx += 1
                    continue
                label = header_text(line)
                if idx + 1 < len(rest) and rest[idx + 1][0] == "data":
                    value_line = rest[idx + 1][1]
                    value = (
                        value_line.split("|", 1)[1].strip()
                        if "|" in value_line
                        else value_line.strip()
                    )
                    idx += 2
                else:
                    value = ""
                    warnings.append(f"row label '{label}' has no matching value line; padded with \"\"")
                    idx += 1
                rows.append([label, value])
            if rows:
                return headers, rows, warnings

    # Shape 3 (split rows): N leading headers, then rows that may span several
    # lines. A line WITHOUT a leading pipe starts a new row; a line WITH one
    # continues the row in progress. This is what recovers the search-condition
    # and validation tables whose first cell sits alone on its line.
    # || Forma 3 (filas partidas): N headers al inicio, luego filas que pueden
    # abarcar varias líneas. Una línea SIN pipe inicial empieza una fila nueva;
    # una CON pipe inicial continúa la fila en curso. Esto es lo que recupera
    # las tablas de condición de búsqueda y de validaciones cuya primera celda
    # queda sola en su línea.
    if leading >= 2 and tail:
        headers = [header_text(line) for _kind, line in tokens[:leading]]
        rows = []
        current: list[str] = []

        def flush() -> None:
            if not current:
                return
            if len(current) < len(headers):
                warnings.append(
                    f"row '{' | '.join(current)[:70]}' has {len(current)} cell(s), expected "
                    f'{len(headers)}; padded with ""'
                )
                current.extend([""] * (len(headers) - len(current)))
            elif len(current) > len(headers):
                warnings.append(
                    f"row '{' | '.join(current)[:70]}' has {len(current)} cell(s), expected "
                    f"{len(headers)}; extra cell(s) dropped"
                )
            rows.append(current[: len(headers)])

        for _kind, line in tail:
            stripped = line.strip()
            if not stripped:
                continue
            cells = [cell.strip() for cell in stripped.split("|")]
            if stripped.startswith("|"):
                # The leading pipe marks a continuation, not an empty first cell.
                # || El pipe inicial marca una continuación, no una primera celda vacía.
                cells = cells[1:]
                current.extend(cells)
            else:
                flush()
                current = list(cells)
        flush()

        if rows:
            return headers, rows, warnings

    return None


def _is_italic_label(text: str) -> bool:
    return bool(ITALIC_LABEL.match(text.strip()))


def _quoted_header(line: str) -> str | None:
    if "|" in line:
        return None
    match = QUOTED_HEADER_LINE.match(line)
    return match.group(1) if match else None


def _read_unpiped_block(
    lines: list[str], start: int
) -> tuple[int, list[str], list[tuple[str, list[str]]]] | None:
    """Read the fourth broken shape starting at ``start``, or return None.

    N non-italic ``####`` headers are the columns; every ``####`` after them is
    a row label, and the plain lines under a label are that row's cells. No
    pipe is involved anywhere, which is exactly why the three piped shapes miss
    it and the section ends up chunked as narrative — one loose chunk per cell,
    with the field name severed from its description.

    || Lee la cuarta forma rota que empieza en ``start``, o devuelve None. N
    headers ``####`` no itálicos son las columnas; todo ``####`` posterior es
    una etiqueta de fila, y las líneas planas bajo una etiqueta son las celdas
    de esa fila. No hay ningún pipe, que es justo por qué las tres formas con
    pipes no la ven y la sección termina troceada como narrativa — un chunk
    suelto por celda, con el nombre del campo separado de su descripción.
    """
    total = len(lines)
    headers: list[str] = []
    cursor = start
    while cursor < total:
        if not lines[cursor].strip():
            cursor += 1
            continue
        text = _quoted_header(lines[cursor])
        if text is None or _is_italic_label(text):
            break
        headers.append(_strip_emphasis(text))
        cursor += 1
    if len(headers) < 2 or cursor >= total:
        return None

    rows: list[tuple[str, list[str]]] = []
    while cursor < total:
        if not lines[cursor].strip():
            cursor += 1
            continue
        label = _quoted_header(lines[cursor])
        if label is None:
            break
        cursor += 1
        values: list[str] = []
        while cursor < total:
            line = lines[cursor]
            if line.strip() and (_quoted_header(line) is not None or line.lstrip().startswith("##")):
                break
            if line.strip():
                values.append(line.strip())
            cursor += 1
        rows.append((_strip_emphasis(label), values))

    while rows and not rows[-1][1] and not rows[-1][0]:
        rows.pop()
    if len(rows) < 2 or not any(values for _label, values in rows):
        return None
    return cursor, headers, rows


def _unpiped_value_cells(values: list[str]) -> list[str]:
    """Split a row's value lines into cells.

    A continuation line often opens with the export's leftover cell separator
    (``| Se incluye la agencia...``). That pipe is a separator, not content, and
    a lone ``\\`` between the label and its value is a line-break artifact.

    || Parte las líneas de valor de una fila en celdas. Una línea de
    continuación suele abrir con el separador de celda que dejó el export; ese
    pipe es un separador, no contenido, y un ``\\`` solo entre la etiqueta y su
    valor es un artefacto de salto de línea.
    """
    cells: list[str] = []
    for value in values:
        text = value.strip().removeprefix("|")
        for part in text.split("|"):
            part = part.strip()
            if part and part.strip("\\"):
                cells.append(part)
    return cells


def _unpiped_rows_are_symmetric(headers: list[str], rows: list[tuple[str, list[str]]]) -> bool:
    """Whether the rows line up with the columns well enough to repair.

    A row must supply exactly one value per non-label column, or none at all —
    a label with no values is a group divider (``_Parte repetitiva_``) and is
    kept as a label-only row. A two-column table is the easy case: everything
    under the label is the single description cell.

    Asymmetric blocks are NOT repaired. Padding a short row at the end would
    put a value in the wrong column — in `mer001.md` the flag ``No`` would land
    under *Tipo de Raíz del Error* instead of *Temporal*, asserting a business
    fact the document never states. A row left unrepaired is a gap; a row
    repaired wrong is a lie.

    || Si las filas se alinean con las columnas lo bastante como para reparar.
    Una fila debe aportar exactamente un valor por columna que no sea la
    etiqueta, o ninguno — una etiqueta sin valores es un divisor de grupo y se
    conserva como fila solo-etiqueta. Una tabla de dos columnas es el caso
    fácil: todo lo que está bajo la etiqueta es la única celda de descripción.

    Los bloques asimétricos NO se reparan. Rellenar una fila corta al final
    pondría un valor en la columna equivocada — en `mer001.md` la bandera ``No``
    caería bajo *Tipo de Raíz del Error* en vez de *Temporal*, afirmando un
    hecho de negocio que el documento nunca dice. Una fila sin reparar es un
    hueco; una fila mal reparada es una mentira.
    """
    if len(headers) == 2:
        return True
    expected = len(headers) - 1
    return all(len(_unpiped_value_cells(values)) in (0, expected) for _label, values in rows)


def _unpiped_row_cells(headers: list[str], label: str, values: list[str]) -> list[str]:
    cells = _unpiped_value_cells(values)
    if len(headers) == 2:
        # Everything under the label is one description cell.
        # || Todo lo que está bajo la etiqueta es una única celda de descripción.
        return [label, " ".join(cells)]
    row = [label, *cells]
    return row + [""] * (len(headers) - len(row))


def _find_unpiped_blocks(
    lines: list[str], claimed: list[tuple[int, int]]
) -> list[tuple[int, int, list[str], list[list[str]]]]:
    """Find every unpiped header/label block outside the regions already claimed.

    Runs as a second pass so the three piped shapes keep the behaviour they
    have; a region one of them already matched is never looked at again.

    || Encuentra cada bloque sin pipes de header/etiqueta fuera de las regiones
    ya tomadas. Corre como segunda pasada para que las tres formas con pipes
    conserven el comportamiento que ya tienen; una región que alguna de ellas
    ya matcheó no se vuelve a mirar.
    """
    found: list[tuple[int, int, list[str], list[list[str]]]] = []
    index = 0
    total = len(lines)
    while index < total:
        if any(start <= index < end for start, end in claimed):
            index += 1
            continue
        text = _quoted_header(lines[index])
        if text is None or _is_italic_label(text):
            index += 1
            continue
        read = _read_unpiped_block(lines, index)
        if read is None:
            index += 1
            continue
        end, headers, rows = read
        if any(start < end and index < stop for start, stop in claimed):
            index = end
            continue
        if not _unpiped_rows_are_symmetric(headers, rows):
            # Visible rather than invisible: a table that is still being lost
            # says so, with the headers that identify it.
            # || Visible en vez de invisible: una tabla que se sigue perdiendo
            # lo dice, con los encabezados que la identifican.
            log.warning(
                "unpiped_table_not_repaired",
                headers=headers,
                rows=len(rows),
                reason="rows do not line up with the columns; padding would put a value in the wrong column",
            )
            index = end
            continue
        found.append((index, end, headers, [_unpiped_row_cells(headers, label, values) for label, values in rows]))
        index = end
    return found


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    def esc(cell: str) -> str:
        return cell.replace("|", "\\|").replace("\n", " ").strip()

    header_row = "| " + " | ".join(esc(h) for h in headers) + " |"
    separator_row = "|" + "|".join(" --- " for _ in headers) + "|"
    data_rows = ["| " + " | ".join(esc(c) for c in row) + " |" for row in rows]
    return "\n".join([header_row, separator_row, *data_rows])


def repair_broken_tables_with_trace(text: str) -> tuple[str, list[RepairedTable]]:
    """Repair broken table blocks, returning the fixed text plus a trace of each repair.

    || Repara los bloques de tabla rotos, devolviendo el texto arreglado más una traza de cada reparación.
    """
    lines = text.split("\n")
    kinds = [_classify_line(line) for line in lines]
    blocks = _find_candidate_blocks(lines, kinds)

    # Second pass for the unpiped shape, over what the first one did not claim,
    # then both merged in source order so the splice below stays sequential.
    # || Segunda pasada para la forma sin pipes, sobre lo que la primera no
    # tomó, y las dos fundidas en orden de la fuente para que el empalme de
    # abajo siga siendo secuencial.
    unpiped = {
        start: (end, headers, rows) for start, end, headers, rows in _find_unpiped_blocks(lines, blocks)
    }
    blocks = sorted([*blocks, *((start, end) for start, (end, _h, _r) in unpiped.items())])

    traces: list[RepairedTable] = []
    out_lines: list[str] = []
    cursor = 0
    for start, end in blocks:
        if start in unpiped:
            _end, headers, rows = unpiped[start]
            warnings = []
        else:
            parsed = _parse_block(lines[start:end])
            if parsed is None:
                continue
            headers, rows, warnings = parsed
        raw_original = "\n".join(lines[start:end])
        repaired_markdown = _render_table(headers, rows)

        out_lines.extend(lines[cursor:start])
        out_lines.append(repaired_markdown)
        cursor = end

        for warning in warnings:
            log.warning("broken_table_repaired_with_gap", detail=warning)
        traces.append(
            RepairedTable(
                raw_original=raw_original,
                repaired_markdown=repaired_markdown,
                headers=headers,
                warnings=warnings,
            )
        )

    out_lines.extend(lines[cursor:])
    return "\n".join(out_lines), traces


def repair_broken_tables(text: str) -> str:
    """Repair broken table blocks in ``text``, returning only the fixed text.

    || Repara los bloques de tabla rotos en ``text``, devolviendo solo el texto arreglado.
    """
    fixed_text, _ = repair_broken_tables_with_trace(text)
    return fixed_text

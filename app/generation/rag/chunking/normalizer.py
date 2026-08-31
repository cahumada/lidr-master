"""Text normalization for functional-spec markdown documents.

Two independent concerns live here: line-ending normalization (source files
are Windows exports, ``\\r\\n``) and repair of a recurring export bug where a
2-column table lost its ``| --- | --- |`` separator row and had its column
headers exported as ``####`` headings instead of a table header row.

Two broken shapes show up in the real corpus, both handled by
:func:`repair_broken_tables`:

* **Simple** — two ``####`` headers, then every data row on its own
  ``label |  value`` line (CA014 "Ramos generales / Vida", CA001 "Tipo de
  registro / Transacción" x2).
* **Paired** — two ``####`` headers, then each row's label repeated as its
  own ``####`` heading followed by a ``|  value`` line with no left cell
  (CA001 "Tipo de inicio de vigencia / Fecha a mostrar", 5 rows).

Both are reconstructed into a single, valid markdown table.

|| Normalización de texto para los documentos markdown de especificación
funcional. Aquí viven dos responsabilidades independientes: normalización de
fin de línea (los archivos fuente son exports de Windows, ``\\r\\n``) y la
reparación de un bug de exportación recurrente donde una tabla de 2 columnas
perdió su fila separadora ``| --- | --- |`` y sus encabezados de columna
quedaron exportados como headings ``####`` en vez de fila de tabla.

Aparecen dos formas rotas en el corpus real, ambas manejadas por
:func:`repair_broken_tables`:

* **Simple** — dos headers ``####``, luego cada fila de datos en su propia
  línea ``etiqueta |  valor`` (CA014 "Ramos generales / Vida", CA001 "Tipo
  de registro / Transacción" x2).
* **Pareada** — dos headers ``####``, luego la etiqueta de cada fila
  repetida como su propio heading ``####`` seguido de una línea
  ``|  valor`` sin celda izquierda (CA001 "Tipo de inicio de vigencia /
  Fecha a mostrar", 5 filas).

Ambas se reconstruyen en una única tabla markdown válida.
"""

from __future__ import annotations

import re

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger()

HEADER_LINE = re.compile(r"^####\s+(.*\S)\s*$")
SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")

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

    traces: list[RepairedTable] = []
    out_lines: list[str] = []
    cursor = 0
    for start, end in blocks:
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

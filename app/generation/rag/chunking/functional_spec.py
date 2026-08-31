"""Hybrid chunker for Visual Time functional-spec markdown documents.

The 30 functional modules of the corpus (policies, life, claims, collections,
maintenance, ...) do NOT share one fixed section layout — headings vary a lot
across modules (``Función`` vs ``Función general``, ``Efecto`` vs ``Proceso``,
``Parámetros de entrada``, ``Información técnica``, ...), and some documents
have no recognizable heading structure at all. So section discovery is
GENERIC: every H2 heading in the document becomes its own section (in source
order), whatever its name — nothing is silently dropped for not matching a
fixed list of known headings. What a section's own name does NOT determine is
its chunking strategy; that is decided by the shape of its content instead:

* **Type A — tables**: a section whose body IS a markdown table and nothing
  else (this is what ``Campos``/``Validaciones`` look like, but so does e.g. a
  ``Parámetros de entrada`` table in a batch-process document — the same rule
  catches both). One row = one chunk: a field/rule/error-code triple is an
  atomic, self-contained fact, same as the course's "1 component = 1 chunk"
  pattern applied to table rows instead of JSON components. Any table
  recovered by :mod:`app.generation.rag.chunking.normalizer` is also included,
  wherever it appears.
* **Type B — narrative**: everything else (prose, bullet lists, or prose with
  a small embedded table — that embedded table is pulled out as its own Type
  A chunk, the surrounding prose still chunks as Type B). One top-level
  bullet = one chunk, together with all of its nested children (a child is
  never separated from its parent). If a section as a whole is small, it
  stays a single chunk. If a top-level bullet alone exceeds the token cap,
  chunking descends one level and repeats; a final sentence-boundary split is
  the last-resort safety net for the rare leaf that still doesn't fit.

No overlap, no fixed-size splitting as a general strategy — the document's
own structure gives the boundaries. Hierarchical/semantic chunking is future
work, not implemented here.

Section names are kept in Spanish throughout this module: they are the
literal H2 headings of the source documents, not code identifiers, and
translating them would break traceability back to the text. ``chunk_id``
slugs are derived directly from that Spanish heading text (ASCII-folded,
lowercased) rather than through a hand-maintained English translation table —
with headings this open-ended across 30 modules, a fixed dictionary doesn't
scale; a generated slug does.

Placement mirrors ``app/generation/rag/chunking/structural.py`` on the
``session_16`` branch of LIDR-academy/ai-engineering: one file per chunking
strategy, next to :mod:`app.generation.rag.chunking.base`.

|| Chunker híbrido para los documentos markdown de especificación funcional
de Visual Time. Los 30 módulos funcionales del corpus (policies, life,
claims, collections, maintenance, ...) NO comparten un layout de secciones
fijo — los headings varían mucho entre módulos (``Función`` vs. ``Función
general``, ``Efecto`` vs. ``Proceso``, ``Parámetros de entrada``,
``Información técnica``, ...), y algunos documentos no tienen ninguna
estructura de heading reconocible. Por eso la detección de secciones es
GENÉRICA: cada heading H2 del documento se vuelve su propia sección (en el
orden de la fuente), sea cual sea su nombre — nada se descarta en silencio
por no matchear una lista fija de headings conocidos. Lo que el nombre de
una sección NO determina es su estrategia de chunking; eso lo decide la
forma de su contenido:

* **Tipo A — tablas**: una sección cuyo cuerpo ES una tabla markdown y nada
  más (así se ven ``Campos``/``Validaciones``, pero también una tabla de
  ``Parámetros de entrada`` en un documento de proceso batch — la misma
  regla agarra ambos casos). Una fila = un chunk: una tripleta
  campo/regla/código-de-error es un hecho atómico y autocontenido, igual
  que el patrón del curso "1 componente = 1 chunk" aplicado a filas de
  tabla en vez de componentes JSON. Cualquier tabla recuperada por
  :mod:`app.generation.rag.chunking.normalizer` también se incluye, donde
  aparezca.
* **Tipo B — narrativa**: todo lo demás (prosa, listas de bullets, o prosa
  con una mini-tabla embebida — esa mini-tabla se extrae como su propio
  chunk Tipo A, la prosa alrededor sigue troceándose como Tipo B). Un
  bullet de primer nivel = un chunk, junto con todos sus hijos anidados (un
  hijo nunca se separa de su padre). Si una sección completa es chica,
  queda como un único chunk. Si un bullet de primer nivel por sí solo
  supera el techo de tokens, el chunking baja un nivel y repite; un split
  final por límite de oración es la red de seguridad de último recurso
  para la rara hoja que aun así no entra.

Sin overlap, sin fixed-size splitting como estrategia general — la
estructura del propio documento da los límites. Chunking
jerárquico/semántico queda como trabajo futuro, no implementado acá.

Los nombres de sección se mantienen en español en todo este módulo: son
los headings H2 literales de los documentos fuente, no identificadores de
código, y traducirlos rompería la trazabilidad hacia el texto. Los slugs
de ``chunk_id`` se derivan directo de ese texto en español (pasado a
ASCII, en minúscula) en vez de una tabla de traducción al inglés
mantenida a mano — con headings tan abiertos en 30 módulos, un diccionario
fijo no escala; un slug generado sí.

La ubicación replica ``app/generation/rag/chunking/structural.py`` en la
rama ``session_16`` de LIDR-academy/ai-engineering: un archivo por
estrategia de chunking, junto a :mod:`app.generation.rag.chunking.base`.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import structlog

from app.generation.rag.chunking.base import count_tokens
from app.generation.rag.chunking.normalizer import (
    normalize_line_endings,
    repair_broken_tables_with_trace,
)
from app.generation.rag.navigation import UNRESOLVED, NavigationLocation, NavigationTree
from app.generation.rag.schemas import (
    Chunk,
    ChunkedDocument,
    ChunkMetadata,
    DocumentKind,
    Reference,
)
from app.generation.rag.taxonomy import classify_transaction_type

log = structlog.get_logger()

NARRATIVE_TOKEN_CAP = 500

# --- Transaction id blocks -------------------------------------------------
# The corpus writes a block's own id as a standalone line, in four observed
# markup forms: `**(CODE)**` (336 files), **`(CODE)`** (24), `(CODE)` (2), plus
# one malformed. Codes are NOT always [A-Z]{2,4}\d{3}: real ones include
# BC005_k, VI7501_A, CA13-1 and the digitless root MENU.
# || El corpus escribe el id propio de un bloque como una línea sola, en cuatro
# formas de marcado observadas: `**(CODE)**` (336 archivos), **`(CODE)`** (24),
# `(CODE)` (2), más una malformada. Los códigos NO son siempre
# [A-Z]{2,4}\d{3}: los reales incluyen BC005_k, VI7501_A, CA13-1 y la raíz sin
# dígitos MENU.
_ID_MARK = r"[\s\\`*]*"
# A code with digits: CA014, CA001k, CPL500, BC005_k, VI7501_A, CA13-1.
# || Un código con dígitos.
_CODE_WITH_DIGITS = r"[A-Z]{2,4}\d{1,5}(?:[_-]?[A-Za-z0-9]{1,3})?"
# A digitless, letters-only code. Only accepted on a standalone id line: in
# running prose `(CAE)` / `(PAE)` are variable names, not transaction ids, and
# accepting them inline would invent ids.
# || Un código sin dígitos, solo letras. Se acepta únicamente en una línea de
# id sola: en prosa corrida `(CAE)` / `(PAE)` son nombres de variable, no ids
# de transacción, y aceptarlos inline inventaría ids.
_CODE_LETTERS_ONLY = r"[A-Z]{3,6}"

# Standalone id line — the authoritative form. Permissive about the code.
# || Línea de id sola — la forma autoritativa. Permisiva con el código.
ID_LINE_PATTERN = re.compile(
    rf"^{_ID_MARK}\({_ID_MARK}({_CODE_WITH_DIGITS}|{_CODE_LETTERS_ONLY}){_ID_MARK}\){_ID_MARK}$",
    re.MULTILINE,
)
# Inline fallback, for a block whose id is not on a line of its own. Strict:
# digits required, so prose in parentheses is not mistaken for an id.
# || Fallback inline, para un bloque cuyo id no está en una línea propia.
# Estricto: exige dígitos, así la prosa entre paréntesis no se confunde con un id.
DOCUMENT_ID_PATTERN = re.compile(rf"\(`?\*{{0,2}}({_CODE_WITH_DIGITS})\*{{0,2}}`?\)")

# A `_k` / `_K` suffix marks the key-request companion of a main transaction.
# || Un sufijo `_k` / `_K` marca el acompañante de solicitud de clave de una
# transacción principal.
KEY_REQUEST_SUFFIX = re.compile(r"^(?P<base>.+?)_[kK]$")

TITLE_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
H1_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
H2_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

# Inline sibling-transaction references, quoted in backticks: `CA003`, `CAC011`.
# Deliberately anchored so it never matches the document's own id block
# (`**(CA004)**`) — a leading '(' after the optional bold markers breaks the match.
# || Referencias inline a transacciones hermanas, citadas entre backticks:
# `CA003`, `CAC011`. Anclado a propósito para que nunca matchee el propio
# bloque de id del documento (`**(CA004)**`) — un '(' inicial después de los
# marcadores de negrita opcionales rompe el match.
INLINE_TRANSACTION_PATTERN = re.compile(r"`\*{0,2}([A-Z]{2,4}\d{3}[A-Za-z]?)\*{0,2}`")
# Footnote-style tags: <DF009>, </DF009>, tolerating the stray space seen in
# some exports ("< DF009>").
# || Tags tipo nota al pie: <DF009>, </DF009>, tolerando el espacio suelto
# que aparece en algunos exports ("< DF009>").
FOOTNOTE_TAG_PATTERN = re.compile(r"<\s*/?\s*([A-Z]{2,4}\d{3})\s*>")

# Links to sibling documents, by their exported HTML filename (`ca047.html`).
# || Enlaces a documentos hermanos, por su nombre de archivo HTML exportado.
HTML_LINK_PATTERN = re.compile(r"([A-Za-z0-9_\-]+)\.html")

TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")

# Label used for the (rare) implicit section made of whatever prose sits
# before the first H2 heading — the corpus is otherwise all-Spanish, so this
# stays consistent with that rather than reading as a code identifier.
# || Etiqueta para la (rara) sección implícita formada por la prosa que
# queda antes del primer heading H2 — el corpus es todo en español, así que
# esto se mantiene consistente en vez de leerse como un identificador de código.
INTRO_SECTION_LABEL = "Introducción"

_SLUG_INVALID = re.compile(r"[^a-z0-9]+")

_BULLET_LINE = re.compile(r"^(\s*)[*\-+]\s+\S")
_BULLET_PREFIX = re.compile(r"^(\s*)[*\-+·§]\s*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.;:])\s+")


def _slugify(heading: str) -> str:
    """ASCII, lowercase, underscored slug for ``chunk_id`` — see module docstring.

    || Slug en ASCII, minúscula, con guiones bajos para ``chunk_id`` — ver el docstring del módulo.
    """
    ascii_text = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_INVALID.sub("_", ascii_text.lower()).strip("_")
    return slug or "section"


def _is_junk_heading(heading: str) -> bool:
    """True for placeholder headings like ``.`` seen in a few source exports.

    || True para headings placeholder como ``.`` que aparecen en algunos exports fuente.
    """
    return heading.strip(". \t") == ""


def extract_child_links(text: str) -> list[str]:
    """Document codes this text links to, de-duplicated, in order of appearance.

    The corpus links to sibling documents by their exported HTML filename
    (``ca047.html``), so the code is the filename stem, uppercased.

    || Códigos de documento a los que este texto enlaza, sin duplicados, en
    orden de aparición. El corpus enlaza a documentos hermanos por su nombre de
    archivo HTML exportado (``ca047.html``), así que el código es el stem del
    nombre, en mayúscula.
    """
    seen: dict[str, None] = {}
    for match in HTML_LINK_PATTERN.finditer(text):
        seen.setdefault(match.group(1).upper(), None)
    return list(seen)


def classify_document_kind(
    text: str, sections: list[tuple[str, str]], *, min_links: int, min_density: float
) -> DocumentKind:
    """Whether this document is a chapter/navigation node rather than content.

    Requires BOTH no pure-table section AND a high density of links to other
    documents. Either signal alone misfires: there are short content documents
    with no table, and content documents that cite several siblings.

    The thresholds are calibrated, not derived — see the change's design note.
    They are deliberately conservative, because the two errors are not
    symmetric: marking a real index as content only leaves some low-value
    chunks, while marking real content as an index would push business rules
    out of the way.

    || Si este documento es un nodo capítulo/navegación en vez de contenido.
    Exige AMBAS cosas: ninguna sección de tabla pura Y alta densidad de enlaces
    a otros documentos. Cualquiera de las dos señales sola falla: hay
    documentos de contenido cortos sin tabla, y documentos de contenido que
    citan varios hermanos.

    Los umbrales están calibrados, no derivados — ver la nota de diseño del
    cambio. Son conservadores a propósito, porque los dos errores no son
    simétricos: marcar un índice real como contenido solo deja algunos chunks
    de bajo valor, mientras marcar contenido real como índice correría reglas
    de negocio del camino.
    """
    if any(_is_pure_table_section(body) for _heading, body in sections):
        return "content"
    links = len(HTML_LINK_PATTERN.findall(text))
    if links < min_links:
        return "content"
    words = max(1, len(text.split()))
    density = links / words * 100
    return "index" if density >= min_density else "content"


def _is_pure_table_section(body: str) -> bool:
    """True when a section's body IS a markdown table and nothing else —
    the shape that decides Type A (row) chunking, regardless of the
    section's own heading name.

    || True cuando el cuerpo de una sección ES una tabla markdown y nada
    más — la forma que decide el chunking Tipo A (por fila), sin importar
    el nombre del heading de la sección.
    """
    lines = [line for line in body.strip("\n").split("\n") if line.strip() != ""]
    if len(lines) < 2:
        return False
    if not (TABLE_ROW.match(lines[0]) and SEPARATOR_ROW.match(lines[1])):
        return False
    return all(TABLE_ROW.match(line) for line in lines[2:])


def _strip_emphasis(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^[*_]+|[*_]+$", "", text)
    return text.strip()


def _block_head(text: str) -> str:
    """The text of a block before its first H2 — where its own id block lives.

    || El texto de un bloque antes de su primer H2 — donde vive su bloque de id propio.
    """
    match = H2_PATTERN.search(text)
    return text[: match.start()] if match else text


def extract_document_id(text: str, fallback: str) -> str:
    """Extract the transaction id from a block's head (before its first H2).

    Tries the standalone id line first (the authoritative form), then the
    stricter inline pattern. Restricted to the head so a reference to another
    document later in the text (e.g. ``(CA021)`` in a "Notas" paragraph) is
    never mistaken for this block's own id.

    || Extrae el id de la transacción de la cabecera de un bloque (antes de su
    primer H2). Prueba primero la línea de id sola (la forma autoritativa), y
    después el patrón inline más estricto. Restringido a la cabecera para que
    una referencia a otro documento más adelante en el texto (ej. ``(CA021)``
    en un párrafo de "Notas") nunca se confunda con el id propio del bloque.
    """
    head = _block_head(text)
    match = ID_LINE_PATTERN.search(head) or DOCUMENT_ID_PATTERN.search(head)
    return match.group(1) if match else fallback


def split_transaction_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Segment a document into its transaction blocks, on standalone id lines.

    Returns ``(preamble, [(code, block_text), ...])``. An empty block list means
    the document declares no id on a line of its own and SHOULD be treated as a
    single block by the caller.

    Segmentation keys on the **id line**, not on ``# `` (H1). H1 is not a
    reliable delimiter: the export also emits ``# `` for bullet continuation
    lines (``# · _Adicionalmente..._``, ``# § _Se construye..._`` in
    `accounting/cp002.md`), so splitting on H1 would invent blocks. Each id
    line is instead extended backwards to the nearest preceding H1 — its title
    — without crossing the previous id line.

    || Segmenta un documento en sus bloques de transacción, por líneas de id
    solas. Devuelve ``(preámbulo, [(código, texto_bloque), ...])``. Una lista
    de bloques vacía significa que el documento no declara ningún id en una
    línea propia y el llamador DEBE tratarlo como un bloque único.

    La segmentación se apoya en la **línea de id**, no en ``# `` (H1). H1 no es
    un delimitador confiable: el export también emite ``# `` para líneas de
    continuación de bullets, así que partir por H1 inventaría bloques. Cada
    línea de id se extiende hacia atrás hasta el H1 más cercano que la precede
    —su título— sin cruzar la línea de id anterior.
    """
    id_matches = list(ID_LINE_PATTERN.finditer(text))
    if not id_matches:
        return "", []

    h1_positions = [m.start() for m in H1_PATTERN.finditer(text)]

    starts: list[int] = []
    previous_boundary = 0
    for match in id_matches:
        candidates = [p for p in h1_positions if previous_boundary <= p < match.start()]
        starts.append(candidates[-1] if candidates else match.start())
        previous_boundary = match.end()

    blocks: list[tuple[str, str]] = []
    for idx, match in enumerate(id_matches):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(text)
        blocks.append((match.group(1), text[starts[idx] : end]))

    return text[: starts[0]], blocks


def resolve_file_level_code(filename: str, found_codes: list[str]) -> str:
    """The code to attribute content that declares no id of its own.

    Prefers the filename stem when it names one of the codes the file actually
    declares; else the sole declared code, since a file declaring exactly one
    transaction leaves no ambiguity; else the stem. This is what stops
    `accounting_cpl500.md` from labelling its content `ACCOUNTING_CPL500` when
    the document itself says `CPL500`.

    || El código con el que atribuir contenido que no declara id propio.
    Prefiere el stem del nombre de archivo cuando nombra uno de los códigos que
    el archivo realmente declara; si no, el único código declarado, porque un
    archivo que declara exactamente una transacción no deja ambigüedad; si no,
    el stem. Esto es lo que evita que `accounting_cpl500.md` etiquete su
    contenido como `ACCOUNTING_CPL500` cuando el documento dice `CPL500`.
    """
    stem = Path(filename).stem.upper()
    unique = list(dict.fromkeys(found_codes))
    if stem in unique:
        return stem
    if len(unique) == 1:
        return unique[0]
    return stem


def resolve_parent_transaction_code(code: str, found_codes: list[str]) -> str | None:
    """The main transaction of a ``_k`` key-request companion, or None.

    Only returned when the base code is declared in the SAME file. Without the
    `WINDOWS` tree there is no evidence for a cross-file parent, and inventing
    one would assert a relation nobody verified.

    || La transacción principal de un acompañante ``_k`` de solicitud de clave,
    o None. Solo se devuelve cuando el código base está declarado en el MISMO
    archivo. Sin el árbol de `WINDOWS` no hay evidencia de un padre en otro
    archivo, e inventarlo afirmaría una relación que nadie verificó.
    """
    match = KEY_REQUEST_SUFFIX.match(code)
    if not match:
        return None
    base = match.group("base")
    return base if base in set(found_codes) else None


def extract_document_title(text: str) -> str:
    """Extract the document title from the first H1 line, emphasis stripped.

    Not every document in the corpus has a ``# `` heading (CA014 does not —
    its title is a bare first line); fall back to the first non-blank line.

    || Extrae el título del documento desde la primera línea H1, sin marcas
    de énfasis. No todos los documentos del corpus tienen un heading
    ``# `` (CA014 no lo tiene — su título es la primera línea pelada);
    si no hay heading, se usa la primera línea no vacía.
    """
    match = TITLE_PATTERN.search(text)
    if match:
        return _strip_emphasis(match.group(1))
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # A section heading is not the title.
        # || Un heading de sección no es el título.
        if stripped.startswith("#"):
            continue
        # Nor is the block's own id line: taking it as the title put
        # `[Documento: OP010 - `**(OP010)**`]` in the contextual header of 2968
        # chunks, saying nothing about what the transaction is.
        # || Ni la línea de id propia del bloque: tomarla como título ponía
        # `[Documento: OP010 - `**(OP010)**`]` en el header contextual de 2968
        # chunks, sin decir nada de qué hace la transacción.
        if ID_LINE_PATTERN.match(stripped):
            continue
        return _strip_emphasis(stripped)
    return ""


def content_hash(text: str) -> str:
    """SHA-256 of ``text``, the identity of a piece of content.

    Used at two levels, for the same reason: what did NOT change need not be
    paid for again. A chunk's hash covers exactly the bytes that get embedded,
    so a matching hash between runs means the existing embedding is still
    valid; a document's hash covers its normalized source, so an unchanged
    document can be skipped whole.

    || SHA-256 de ``text``, la identidad de un contenido. Se usa en dos
    niveles, por la misma razón: lo que NO cambió no hay que volver a pagarlo.
    El hash de un chunk cubre exactamente los bytes que se embeben, así que un
    hash igual entre corridas significa que el embedding existente sigue
    siendo válido; el hash de un documento cubre su fuente normalizada, así que
    un documento sin cambios se puede saltear entero.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_block_title(block_text: str) -> str:
    """A transaction block's own title: its H1 heading, or empty.

    Deliberately stricter than :func:`extract_document_title`: a block that
    starts at its own id line has no title of its own, and the first prose line
    of its body is NOT a title — taking it produced headers like
    `[Documento: CA014 - Permite consultar y modificar.]`. The caller falls back
    to the document's title instead.

    || El título propio de un bloque de transacción: su heading H1, o vacío.
    A propósito más estricto que :func:`extract_document_title`: un bloque que
    arranca en su propia línea de id no tiene título propio, y la primera línea
    de prosa de su cuerpo NO es un título — tomarla producía headers como
    `[Documento: CA014 - Permite consultar y modificar.]`. El llamador cae al
    título del documento.
    """
    match = TITLE_PATTERN.search(block_text)
    return _strip_emphasis(match.group(1)) if match else ""


def parse_sections(text: str) -> list[tuple[str, str]]:
    """Split the document into ALL of its H2 sections, in source order,
    tolerant of bold/italic markup on the heading itself (e.g.
    ``## **_Campos_**``). No fixed list of recognized headings — see the
    module docstring for why.

    Any real prose sitting before the first H2 (rare — most documents open
    straight with a title + id block) becomes an implicit
    :data:`INTRO_SECTION_LABEL` section; placeholder headings (``.``) and
    empty sections are dropped.

    || Divide el documento en TODAS sus secciones H2, en el orden de la
    fuente, tolerante a marcado de negrita/itálica en el propio heading
    (ej. ``## **_Campos_**``). Sin lista fija de headings reconocidos — ver
    el docstring del módulo para el porqué.

    Cualquier prosa real que quede antes del primer H2 (raro — la mayoría
    de los documentos abren directo con título + bloque de id) se vuelve
    una sección implícita :data:`INTRO_SECTION_LABEL`; headings placeholder
    (``.``) y secciones vacías se descartan.
    """
    matches = list(H2_PATTERN.finditer(text))
    sections: list[tuple[str, str]] = []

    intro_end = matches[0].start() if matches else len(text)
    intro_body = TITLE_PATTERN.sub("", text[:intro_end], count=1)
    intro_body = ID_LINE_PATTERN.sub("", intro_body, count=1).strip("\n")
    first_line = _strip_emphasis(text.strip().split("\n", 1)[0]) if text.strip() else ""
    if intro_body.strip() and intro_body.strip() != first_line:
        sections.append((INTRO_SECTION_LABEL, intro_body))

    for idx, match in enumerate(matches):
        raw_name = _strip_emphasis(match.group(1))
        if _is_junk_heading(raw_name):
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip("\n")
        if not body.strip():
            continue
        sections.append((raw_name, body))

    return sections


def _split_row(line: str) -> list[str]:
    line = line.strip()
    line = line.removeprefix("|")
    line = line.removesuffix("|")
    return [cell.strip() for cell in line.split("|")]


def parse_markdown_table(section_text: str) -> tuple[list[str], list[list[str]]]:
    """Parse a well-formed markdown table (header + separator + data rows).

    || Parsea una tabla markdown bien formada (header + separador + filas de datos).
    """
    lines = [line for line in section_text.strip("\n").split("\n") if line.strip() != ""]
    if len(lines) < 2:
        return [], []
    headers = _split_row(lines[0])
    rows = [_split_row(line) for line in lines[2:] if "|" in line]
    return headers, rows


def _extract_embedded_tables(
    text: str,
) -> tuple[str, list[tuple[list[str], list[list[str]]]]]:
    """Pull well-formed tables out of narrative prose (Type A material that
    happens to live inside a Función/Efecto/Notas section), leaving the rest
    of the prose for bullet chunking.

    || Extrae tablas bien formadas de la prosa narrativa (material Tipo A
    que vive dentro de una sección Función/Efecto/Notas), dejando el resto
    de la prosa para el chunking por bullets.
    """
    lines = text.split("\n")
    tables: list[tuple[list[str], list[list[str]]]] = []
    out_lines: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        if TABLE_ROW.match(lines[i]) and i + 1 < n and SEPARATOR_ROW.match(lines[i + 1]):
            headers = _split_row(lines[i])
            j = i + 2
            rows = []
            while j < n and TABLE_ROW.match(lines[j]):
                rows.append(_split_row(lines[j]))
                j += 1
            tables.append((headers, rows))
            i = j
            continue
        out_lines.append(lines[i])
        i += 1
    return "\n".join(out_lines), tables


def extract_references(text: str, self_code: str | None = None) -> list[Reference]:
    """Extract inline sibling-transaction refs and footnote-style tags from a chunk's text.

    || Extrae referencias inline a transacciones hermanas y tags tipo nota
    al pie del texto de un chunk.
    """
    seen: dict[tuple[str, str], Reference] = {}
    for match in INLINE_TRANSACTION_PATTERN.finditer(text):
        code = match.group(1)
        if code == self_code:
            continue
        key = ("inline_transaction", code)
        if key not in seen:
            seen[key] = Reference(
                code=code, type="inline_transaction", context=_line_context(text, match.start())
            )
    for match in FOOTNOTE_TAG_PATTERN.finditer(text):
        code = match.group(1)
        if code == self_code:
            continue
        key = ("footnote_tag", code)
        if key not in seen:
            seen[key] = Reference(
                code=code, type="footnote_tag", context=_line_context(text, match.start())
            )
    return list(seen.values())


def _line_context(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    if end == -1:
        end = len(text)
    return text[start:end].strip()


def _contextual_header(document_id: str, title: str, section: str, bullet_path: str | None = None) -> str:
    section_line = (
        f"[Sección: {section}]" if not bullet_path else f"[Sección: {section} > {bullet_path}]"
    )
    return f"[Documento: {document_id} - {title}]\n{section_line}\n"


def _segment_prose(text: str) -> list[str]:
    """Split prose into top-level units: one per top-level markdown bullet
    (with all deeper-indented/child content attached), and one per
    blank-line-delimited paragraph for everything that isn't part of a
    markdown bullet list (plain prose, and the '·'/'§'/'>' conventions the
    corpus also uses — those never get split mid-statement since each is
    already its own blank-line-separated block in the source).

    || Divide la prosa en unidades de primer nivel: una por cada bullet de
    markdown de primer nivel (con todo el contenido hijo/más indentado
    adjunto), y una por cada párrafo delimitado por línea en blanco para
    todo lo que no forma parte de una lista markdown (prosa simple, y las
    convenciones '·'/'§'/'>' que también usa el corpus — esas nunca se
    parten a mitad de un enunciado porque cada una ya es su propio bloque
    separado por línea en blanco en la fuente).
    """
    lines = text.split("\n")
    n = len(lines)
    bullet_indents = [len(m.group(1)) for line in lines if (m := _BULLET_LINE.match(line))]
    min_indent = min(bullet_indents) if bullet_indents else None

    segments: list[str] = []
    i = 0
    buf_start: int | None = None
    while i < n:
        match = _BULLET_LINE.match(lines[i])
        if match and len(match.group(1)) == min_indent:
            if buf_start is not None:
                segments.append("\n".join(lines[buf_start:i]))
                buf_start = None
            j = i + 1
            while j < n:
                deeper = _BULLET_LINE.match(lines[j])
                if deeper and len(deeper.group(1)) == min_indent:
                    break
                j += 1
            segments.append("\n".join(lines[i:j]))
            i = j
            continue
        if buf_start is None:
            buf_start = i
        i += 1
    if buf_start is not None:
        segments.append("\n".join(lines[buf_start:]))

    final: list[str] = []
    for seg in segments:
        first_line = seg.split("\n", 1)[0]
        if _BULLET_LINE.match(first_line):
            final.append(seg)
        else:
            for para in re.split(r"\n\s*\n", seg):
                para = para.strip("\n")
                if para.strip():
                    final.append(para)
    return final


def _label_for(unit_text: str) -> str:
    first_line = unit_text.strip().split("\n", 1)[0]
    label = _BULLET_PREFIX.sub("", first_line).strip()
    label = _strip_emphasis(label)
    return label[:80]


def _split_by_words(text: str, path: list[str], cap: int, header_tokens: int) -> list[tuple[list[str], str]]:
    """Ultimate fallback: a single run-on clause with no sentence-ending
    punctuation and still over the cap. Packs whole words up to the budget.

    || Último recurso: una única cláusula corrida sin puntuación de fin de
    oración que aun así supera el techo. Empaqueta palabras enteras hasta
    el presupuesto disponible.
    """
    words = text.split()
    if not words:
        return [(path, text)]
    result: list[tuple[list[str], str]] = []
    buf = ""
    for word in words:
        candidate = f"{buf} {word}".strip() if buf else word
        if buf and count_tokens(candidate) + header_tokens > cap:
            result.append((path, buf))
            buf = word
        else:
            buf = candidate
    if buf:
        result.append((path, buf))
    return result


def _split_by_sentences(
    text: str, path: list[str], cap: int, header_tokens: int
) -> list[tuple[list[str], str]]:
    """Last-resort split for a leaf unit that still exceeds the cap and has
    no finer bullet structure left to descend into.

    || Split de último recurso para una unidad hoja que aun así supera el
    techo y no tiene más estructura de bullets a la cual bajar.
    """
    sentences = [s for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]
    if not sentences:
        return [(path, text)]
    result: list[tuple[list[str], str]] = []
    buf = ""
    for sentence in sentences:
        if count_tokens(sentence) + header_tokens > cap:
            if buf:
                result.append((path, buf))
                buf = ""
            result.extend(_split_by_words(sentence, path, cap, header_tokens))
            continue
        candidate = f"{buf} {sentence}".strip() if buf else sentence
        if buf and count_tokens(candidate) + header_tokens > cap:
            result.append((path, buf))
            buf = sentence
        else:
            buf = candidate
    if buf:
        result.append((path, buf))
    return result


def _chunk_units(
    document_id: str, title: str, section: str, units: list[str], path: list[str], cap: int
) -> list[tuple[list[str], str]]:
    """Recursively fit ``units`` under ``cap``, descending one bullet level at a time.

    The token budget for each unit is computed from ITS OWN contextual
    header (which grows with the breadcrumb path as we descend) rather than
    a constant estimated once at the top — otherwise a long ``bullet_path``
    accumulated over several levels silently eats into the token cap.

    || Ajusta ``units`` recursivamente al ``cap``, bajando un nivel de
    bullet a la vez. El presupuesto de tokens de cada unidad se calcula a
    partir de SU PROPIO header contextual (que crece con la ruta de
    breadcrumb a medida que se baja de nivel) en vez de una constante
    estimada una sola vez arriba — si no, un ``bullet_path`` largo
    acumulado en varios niveles se comería en silencio el techo de tokens.
    """
    result: list[tuple[list[str], str]] = []
    for unit_text in units:
        label = _label_for(unit_text)
        new_path = [*path, label] if label else path
        bullet_path = " > ".join(new_path) if new_path else None
        header_tokens = count_tokens(_contextual_header(document_id, title, section, bullet_path))
        if count_tokens(unit_text) + header_tokens <= cap:
            result.append((new_path, unit_text))
            continue
        lines = unit_text.split("\n")
        rest = "\n".join(lines[1:]).strip("\n")
        sub_units = _segment_prose(rest) if rest else []
        if len(sub_units) <= 1:
            result.extend(_split_by_sentences(unit_text, new_path, cap, header_tokens))
        else:
            result.extend(_chunk_units(document_id, title, section, sub_units, new_path, cap))
    return result


# A line that is nothing but markdown structure or an export artifact: a bare
# heading (`###  Proceso`, `#`), or a run of underscores/punctuation (`__`).
# || Una línea que es solo estructura markdown o un artefacto del export: un
# heading pelado (`###  Proceso`, `#`), o una corrida de guiones bajos/puntuación.
_PUNCTUATION_ONLY = re.compile(r"^[\s_\-*~`.#]+$")
_HEADING_LINE = re.compile(r"^#{1,6}\s*(.*)$")


def _is_structure_only(line: str) -> bool:
    """A line that is markdown structure or an artifact, carrying no content.

    A heading counts only when its text is a short LABEL (``###  Proceso``,
    ``#### Campo``). The export also emits ``# `` for bullet continuation lines
    that do carry content (``# § _Se construye el auxiliar concatenando..._``),
    so treating every ``#`` line as structure would delete real rules.

    || Una línea que es estructura markdown o un artefacto, sin contenido. Un
    heading cuenta solo cuando su texto es una ETIQUETA corta. El export también
    emite ``# `` para líneas de continuación de bullets que sí llevan contenido,
    así que tratar toda línea con ``#`` como estructura borraría reglas reales.
    """
    if _PUNCTUATION_ONLY.match(line):
        return True
    match = _HEADING_LINE.match(line)
    if not match:
        return False
    label = _strip_emphasis(match.group(1))
    return len(label.split()) <= 3


def carries_no_information(body: str) -> bool:
    """True when a chunk's content is structure or emptiness, not information.

    The discriminator is NOT length. `No aplica.` and `A petición del usuario.`
    are short but are real answers — with their contextual header they say
    "the execution frequency of CPL500 is: at the user's request". What must go
    is content that says nothing at all: a leftover heading, an export artifact,
    or a table row whose every cell is empty.

    Dropping by length would have deleted 291 real answers along with the noise.

    || True cuando el contenido de un chunk es estructura o vacío, no
    información. El discriminador NO es el largo. `No aplica.` y `A petición del
    usuario.` son cortos pero son respuestas reales — con su header contextual
    dicen "la frecuencia de ejecución de CPL500 es: a petición del usuario". Lo
    que hay que sacar es el contenido que no dice nada: un heading sobrante, un
    artefacto del export, o una fila de tabla con todas sus celdas vacías.

    Descartar por largo habría borrado 291 respuestas reales junto con el ruido.
    """
    stripped = body.strip()
    if not stripped:
        return True
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return True
    # Every line is markdown structure or punctuation.
    # || Cada línea es estructura markdown o puntuación.
    if all(_is_structure_only(line) for line in lines):
        return True
    # A rendered table row: every `header: value` line has an empty value.
    # || Una fila de tabla renderizada: cada línea `header: valor` tiene el valor vacío.
    labelled = [line for line in lines if ":" in line]
    return len(labelled) == len(lines) and all(
        not line.split(":", 1)[1].strip() for line in labelled
    )


def _table_row_chunks(
    headers: list[str],
    rows: list[list[str]],
    document_id: str,
    title: str,
    section: str,
    start_index: int,
) -> list[Chunk]:
    chunks = []
    for offset, row in enumerate(rows):
        cells = row + [""] * (len(headers) - len(row))
        cells = cells[: len(headers)] if len(cells) > len(headers) else cells
        body = "\n".join(f"{h}: {c}" for h, c in zip(headers, cells))
        if carries_no_information(body):
            # A row whose every cell is empty says nothing. Skipping it is not
            # losing business information — there is none to lose.
            # || Una fila con todas sus celdas vacías no dice nada. Saltearla no
            # es perder información de negocio — no hay ninguna que perder.
            continue
        header = _contextual_header(document_id, title, section)
        full_text = header + body
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}::{_slugify(section)}::{start_index + offset}",
                text=full_text,
                metadata=ChunkMetadata(
                    document_id=document_id,
                    document_title=title,
                    section=section,
                    chunk_type="table",
                    field=cells[0] if cells else None,
                ),
                token_count=count_tokens(full_text),
                references=extract_references(full_text, self_code=document_id),
            )
        )
    return chunks


def _chunk_table_section(
    section_text: str, document_id: str, title: str, section: str, start_index: int = 1
) -> list[Chunk]:
    headers, rows = parse_markdown_table(section_text)
    return _table_row_chunks(headers, rows, document_id, title, section, start_index=start_index)


def _chunk_narrative_section(
    section_text: str, document_id: str, title: str, section: str, cap: int, start_index: int = 1
) -> list[Chunk]:
    prose_text, embedded_tables = _extract_embedded_tables(section_text)

    chunks: list[Chunk] = []
    idx = start_index
    for headers, rows in embedded_tables:
        table_chunks = _table_row_chunks(headers, rows, document_id, title, section, start_index=idx)
        chunks.extend(table_chunks)
        idx += len(table_chunks)

    prose_text = prose_text.strip("\n")
    if not prose_text:
        return chunks

    header_tokens = count_tokens(_contextual_header(document_id, title, section))
    if count_tokens(prose_text) + header_tokens <= cap:
        units: list[tuple[list[str], str]] = [([], prose_text)]
    else:
        units = _chunk_units(document_id, title, section, _segment_prose(prose_text), [], cap)

    for path, unit_text in units:
        if carries_no_information(unit_text):
            # A leftover heading or an export artifact. Dropped by CONTENT, not
            # by length: `No aplica.` is short but is a real answer.
            # || Un heading sobrante o un artefacto del export. Se descarta por
            # CONTENIDO, no por largo: `No aplica.` es corto pero es una
            # respuesta real.
            continue
        bullet_path = " > ".join(path) if path else None
        header = _contextual_header(document_id, title, section, bullet_path)
        full_text = header + unit_text.strip()
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}::{_slugify(section)}::{idx}",
                text=full_text,
                metadata=ChunkMetadata(
                    document_id=document_id,
                    document_title=title,
                    section=section,
                    chunk_type="narrative",
                    bullet_path=bullet_path,
                ),
                token_count=count_tokens(full_text),
                references=extract_references(full_text, self_code=document_id),
            )
        )
        idx += 1

    return chunks


class FunctionalSpecChunker:
    """Turns one functional-spec markdown document into table-row chunks
    (any section whose body is a pure markdown table) and bullet chunks
    (everything else) — see the module docstring for how the strategy per
    section is decided.

    || Convierte un documento markdown de especificación funcional en
    chunks de fila de tabla (cualquier sección cuyo cuerpo sea una tabla
    markdown pura) y chunks de bullet (todo lo demás) — ver el docstring
    del módulo para cómo se decide la estrategia por sección.
    """

    def __init__(
        self,
        narrative_token_cap: int = NARRATIVE_TOKEN_CAP,
        index_doc_min_links: int = 5,
        index_doc_min_link_density: float = 3.0,
        navigation_tree: NavigationTree | None = None,
        tenant_id: str = "default",
        doc_version: str = "unversioned",
    ) -> None:
        self._narrative_token_cap = narrative_token_cap
        self._index_doc_min_links = index_doc_min_links
        self._index_doc_min_link_density = index_doc_min_link_density
        # Optional: without the WINDOWS export the chunker behaves exactly as
        # before and resolves no breadcrumb.
        # || Opcional: sin el export de WINDOWS el chunker se comporta igual que
        # antes y no resuelve breadcrumb.
        self._navigation_tree = navigation_tree
        # Version identity stamped onto every chunk, so the vector store can
        # isolate one client and one documentation version in a query.
        # || Identidad de versión estampada en cada chunk, para que el vector
        # store pueda aislar un cliente y una versión de la documentación.
        self._tenant_id = tenant_id
        self._doc_version = doc_version

    def chunk(self, filename: str, raw_content: str) -> list[ChunkedDocument]:
        """Chunk one source file into one entry per transaction it describes.

        || Trocea un archivo fuente en una entrada por cada transacción que describe.
        """
        text = normalize_line_endings(raw_content)
        text, _table_traces = repair_broken_tables_with_trace(text)

        # Document kind is a property of the whole file, not of one block: a
        # chapter node links to its children instead of describing transactions.
        # || La clase de documento es propiedad del archivo entero, no de un
        # bloque: un nodo capítulo enlaza a sus hijos en vez de describir
        # transacciones.
        document_kind = classify_document_kind(
            text,
            parse_sections(text),
            min_links=self._index_doc_min_links,
            min_density=self._index_doc_min_link_density,
        )
        child_links = extract_child_links(text)

        preamble, blocks = split_transaction_blocks(text)

        if not blocks:
            # No id declared on a line of its own: the whole file is one block.
            # || Ningún id declarado en una línea propia: todo el archivo es un bloque.
            document_id = extract_document_id(text, fallback=Path(filename).stem.upper())
            title = extract_document_title(text)
            return [
                self._build(
                    document_id=document_id,
                    title=title,
                    body=text,
                    found_codes=[],
                    document_kind=document_kind,
                    child_links=child_links,
                    is_container=False,
                    counter={},
                )
            ]

        found_codes = [code for code, _body in blocks]
        # Content is accumulated PER document_id, not per block. Several blocks
        # (and the preamble) can resolve to the same transaction, and each must
        # continue one shared per-slug counter — numbering each block from 1
        # independently produced 952 duplicate chunk_ids across 223 files.
        # || El contenido se acumula POR document_id, no por bloque. Varios
        # bloques (y el preámbulo) pueden resolver a la misma transacción, y
        # cada uno debe continuar un único contador por slug compartido —
        # numerar cada bloque desde 1 de forma independiente producía 952
        # chunk_id duplicados en 223 archivos.
        accumulated: dict[str, ChunkedDocument] = {}
        counters: dict[str, dict[str, int]] = {}

        def absorb(document_id: str, title: str, body: str, *, is_container: bool) -> None:
            counter = counters.setdefault(document_id, {})
            existing = accumulated.get(document_id)
            if existing is None:
                accumulated[document_id] = self._build(
                    document_id=document_id,
                    title=title,
                    body=body,
                    found_codes=found_codes,
                    document_kind=document_kind,
                    child_links=child_links,
                    is_container=is_container,
                    counter=counter,
                )
                return
            chunks = self._chunk_block(body, document_id, title, counter)
            self._stamp(
                chunks,
                existing.transaction_type,
                document_kind,
                self._navigation_tree.locate(document_id) if self._navigation_tree else UNRESOLVED,
            )
            # A real transaction block outranks a container-only entry: the
            # preamble was that transaction's own overview, not a separate doc.
            # || Un bloque de transacción real gana sobre una entrada que era
            # solo contenedor: el preámbulo era la introducción de esa misma
            # transacción, no un documento aparte.
            if not is_container and existing.is_container:
                existing.is_container = False
                existing.document_title = title
            existing.chunks.extend(chunks)

        # The preamble describes the family, not one transaction. It is kept
        # rather than discarded (it carries the general Función / Información
        # técnica) and rather than copied into each child.
        # || El preámbulo describe la familia, no una transacción. Se conserva
        # en vez de descartarlo (lleva la Función general / Información técnica)
        # y en vez de copiarlo en cada hijo.
        # A block that starts at its own id line carries no title of its own;
        # it falls back to the document's, so its chunks say what the
        # transaction is instead of repeating its code.
        # || Un bloque que arranca en su propia línea de id no tiene título
        # propio; cae al del documento, así sus chunks dicen qué hace la
        # transacción en vez de repetir su código.
        file_title = extract_document_title(text)

        if parse_sections(preamble):
            container_id = resolve_file_level_code(filename, found_codes)
            absorb(
                container_id,
                extract_block_title(preamble) or file_title,
                preamble,
                is_container=True,
            )

        for code, body in blocks:
            absorb(code, extract_block_title(body) or file_title, body, is_container=False)

        return list(accumulated.values())

    def _build(
        self,
        *,
        document_id: str,
        title: str,
        body: str,
        found_codes: list[str],
        document_kind: DocumentKind,
        child_links: list[str],
        is_container: bool,
        counter: dict[str, int],
    ) -> ChunkedDocument:
        """Assemble one document, stamping the taxonomy onto every chunk.

        The type and kind are stamped after chunking rather than threaded
        through each section-chunking function: they are properties of the
        document, and passing them down five signatures would obscure the
        chunking logic without making anything clearer.

        || Arma un documento, estampando la taxonomía en cada chunk. El tipo y
        la clase se estampan después de trocear en vez de pasarlos por cada
        función de chunking de sección: son propiedades del documento, y
        bajarlos por cinco firmas taparía la lógica de chunking sin aclarar nada.
        """
        location = (
            self._navigation_tree.locate(document_id) if self._navigation_tree else UNRESOLVED
        )
        classification = classify_transaction_type(document_id, is_menu_node=location.is_menu_node)
        chunks = self._chunk_block(body, document_id, title, counter)
        self._stamp(chunks, classification.transaction_type, document_kind, location)
        return ChunkedDocument(
            document_id=document_id,
            document_title=title,
            parent_transaction_code=resolve_parent_transaction_code(document_id, found_codes),
            is_container=is_container,
            transaction_type=classification.transaction_type,
            transaction_type_reason=classification.reason,
            document_kind=document_kind,
            child_links=child_links,
            navigation_path=location.navigation_path,
            is_menu_node=location.is_menu_node,
            content_hash=content_hash(body),
            chunks=chunks,
        )

    def _stamp(
        self,
        chunks: list[Chunk],
        transaction_type: str,
        document_kind: DocumentKind,
        location: NavigationLocation,
    ) -> None:
        """Stamp the document-level facts onto every chunk of a batch.

        ONE place, called from both paths that produce chunks. Having the
        second path (a document absorbing a further block) stamp only a subset
        left 27813 chunks without tenant/version and without breadcrumb —
        silently, because each field looked plausible on its own.

        || Estampa los hechos de nivel documento en cada chunk de un lote. UN
        solo lugar, llamado desde los dos caminos que producen chunks. Que el
        segundo camino (un documento absorbiendo otro bloque) estampara solo un
        subconjunto dejó 27813 chunks sin tenant/versión y sin breadcrumb — en
        silencio, porque cada campo por separado parecía plausible.
        """
        for chunk in chunks:
            chunk.metadata.transaction_type = transaction_type
            chunk.metadata.document_kind = document_kind
            chunk.metadata.module_code = location.module_code
            chunk.metadata.module_name = location.module_name
            chunk.metadata.submodule_code = location.submodule_code
            chunk.metadata.submodule_name = location.submodule_name
            chunk.metadata.tenant_id = self._tenant_id
            chunk.metadata.doc_version = self._doc_version
            # The chunk's hash covers exactly the bytes that get embedded, so a
            # match between runs means the existing embedding is still valid.
            # || El hash del chunk cubre exactamente los bytes que se embeben,
            # así que una coincidencia entre corridas significa que el embedding
            # existente sigue siendo válido.
            chunk.metadata.content_hash = content_hash(chunk.text)

    def _chunk_block(
        self, block_text: str, document_id: str, document_title: str, next_index: dict[str, int]
    ) -> list[Chunk]:
        """Chunk one block's sections, continuing ``next_index`` per section slug.

        The caller owns ``next_index`` so that everything attributed to one
        transaction shares a single counter and no two chunks collide on
        ``chunk_id``.

        || Trocea las secciones de un bloque, continuando ``next_index`` por
        slug de sección. El llamador es dueño de ``next_index`` para que todo lo
        atribuido a una transacción comparta un único contador y ningún par de
        chunks colisione en ``chunk_id``.
        """
        chunks: list[Chunk] = []
        for heading, body in parse_sections(block_text):
            slug = _slugify(heading)
            start_index = next_index.get(slug, 1)
            if _is_pure_table_section(body):
                new_chunks = _chunk_table_section(body, document_id, document_title, heading, start_index)
            else:
                new_chunks = _chunk_narrative_section(
                    body, document_id, document_title, heading, self._narrative_token_cap, start_index
                )
            chunks.extend(new_chunks)
            next_index[slug] = start_index + len(new_chunks)
        return chunks

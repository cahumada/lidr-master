"""Pydantic models for the RAG chunking pipeline. || Modelos Pydantic para el pipeline de chunking de RAG.

Input is one functional-spec markdown document for a Visual Time transaction
(e.g. CA014). Output is a list of chunks ready to embed — no embeddings yet,
that is a separate concern (``generation/rag/embedding/``, not built here).

Placement mirrors the course architecture (``app/generation/rag/schemas.py``
on the ``session_16`` branch of LIDR-academy/ai-engineering): chunk/document
contracts live next to the ``rag`` generation architecture they serve, not
under ``domain/`` (reserved for the cross-cutting conductor contracts) nor
under ``ingestion/`` (reserved for the catalog-driven batch pipeline, which
this project does not use).

|| La entrada es un documento markdown de especificación funcional de una
transacción de Visual Time (ej. CA014). La salida es una lista de chunks
listos para embeber — todavía sin embeddings, eso es una responsabilidad
separada (``generation/rag/embedding/``, no implementada acá).

La ubicación replica la arquitectura del curso (``app/generation/rag/schemas.py``
en la rama ``session_16`` de LIDR-academy/ai-engineering): los contratos de
documento/chunk viven junto a la arquitectura de generación ``rag`` a la que
sirven, no bajo ``domain/`` (reservado para los contratos transversales del
conductor) ni bajo ``ingestion/`` (reservado para el pipeline batch dirigido
por catálogo, que este proyecto no usa).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# "inline_transaction" = backtick-quoted sibling transaction in prose (`CA003`).
# "footnote_tag" = footnote-style tag (<DF009>).
# || "inline_transaction" = transacción hermana citada entre backticks en la
# prosa (`CA003`). "footnote_tag" = tag tipo nota al pie (<DF009>).
ChunkType = Literal["table", "narrative"]
ReferenceType = Literal["inline_transaction", "footnote_tag"]
# "content" = describes a transaction. "index" = a chapter/navigation node that
# mostly links to its children.
# || "content" = describe una transacción. "index" = un nodo capítulo/navegación
# que sobre todo enlaza a sus hijos.
DocumentKind = Literal["content", "index"]


class Reference(BaseModel):
    """A cross-reference to another functional document found inside a chunk.

    Two distinct patterns observed in the corpus share this one model via the
    ``type`` discriminator, instead of two parallel lists on ``Chunk``:
    inline sibling transactions quoted in prose (`` `CA003` ``) and
    footnote-style tags (``<DF009>``).

    || Una referencia cruzada a otro documento funcional encontrada dentro de
    un chunk. Los dos patrones distintos observados en el corpus comparten
    este único modelo mediante el discriminador ``type``, en vez de dos
    listas paralelas en ``Chunk``: transacciones hermanas citadas inline en
    la prosa (`` `CA003` ``) y tags tipo nota al pie (``<DF009>``).
    """

    code: str = Field(description="Referenced document id, e.g. 'CA003', 'DF009'. || Id del documento referenciado, ej. 'CA003', 'DF009'.")
    type: ReferenceType = Field(
        description="'inline_transaction' = backtick-quoted sibling transaction "
        "(`CA003`); 'footnote_tag' = footnote-style tag (<DF009>). "
        "|| 'inline_transaction' = transacción hermana entre backticks "
        "(`CA003`); 'footnote_tag' = tag tipo nota al pie (<DF009>)."
    )
    context: str | None = Field(
        default=None,
        description="The line the reference appears in, for traceability. "
        "|| La línea en la que aparece la referencia, para trazabilidad.",
    )


class ChunkMetadata(BaseModel):
    """Filterable, non-embedded fields that travel alongside a chunk.

    A real ``dict``/``dict[str, Any]`` type renders as a bare ``object`` in
    Swagger's Schema tab (no declared properties to list) — this typed model
    exists so the actual attributes show up there. ``field`` only applies
    when ``chunk_type='table'``; ``bullet_path`` only when
    ``chunk_type='narrative'`` — a chunk carries exactly one of the two.

    || Campos filtrables, no embebidos, que viajan junto a un chunk. Un
    ``dict``/``dict[str, Any]`` real se renderiza como un ``object`` pelado
    en la pestaña Schema de Swagger (no hay propiedades declaradas que
    listar) — este modelo tipado existe para que los atributos reales
    aparezcan ahí. ``field`` solo aplica cuando ``chunk_type='table'``;
    ``bullet_path`` solo cuando ``chunk_type='narrative'`` — un chunk lleva
    exactamente uno de los dos.
    """

    document_id: str = Field(description="Transaction id, e.g. 'CA014'. || Id de la transacción, ej. 'CA014'.")
    document_title: str = Field(description="Document title. || Título del documento.")
    section: str = Field(
        description="Section heading as it appears in the source document "
        "(Función, Efecto, Notas para el programador, Campos, Validaciones). "
        "|| Heading de la sección tal como aparece en el documento fuente "
        "(Función, Efecto, Notas para el programador, Campos, Validaciones)."
    )
    chunk_type: ChunkType
    transaction_type: str = Field(
        default="unknown",
        description="Transaction type from the code's naming convention "
        "(interface / key_request / process_report / query / maintenance / "
        "functional_abm / unknown). || Tipo de transacción según la convención "
        "de nomenclatura del código.",
    )
    document_kind: DocumentKind = Field(
        default="content",
        description="'index' marks a chapter/navigation node so retrieval can "
        "deprioritize it; its chunks are still produced. || 'index' marca un "
        "nodo capítulo/navegación para que el retrieval lo despriorice; sus "
        "chunks se producen igual.",
    )
    # Flat, not nested: the vector store filters by equality. All optional,
    # because the WINDOWS export resolves a path for only part of the corpus —
    # absent must read as absent, never as a guess.
    # || Planos, no anidados: el vector store filtra por igualdad. Todos
    # opcionales, porque el export de WINDOWS resuelve camino solo para parte
    # del corpus — ausente tiene que leerse como ausente, nunca como suposición.
    module_code: str | None = Field(default=None, description="Module code, e.g. 'DMECAR'. || Código de módulo.")
    module_name: str | None = Field(default=None, description="Module name, e.g. 'Pólizas'. || Nombre del módulo.")
    submodule_code: str | None = Field(
        default=None,
        description="Submodule code when the path has that level; absent otherwise. "
        "|| Código de submódulo cuando el camino tiene ese nivel; ausente si no.",
    )
    submodule_name: str | None = Field(default=None, description="Submodule name. || Nombre del submódulo.")
    # Version identity. The manifest is the authoritative declaration (the
    # processing brief says the client identity lives there and is never
    # repeated per unit), but a vector store filters PER ROW: without these on
    # the chunk there is no way to isolate one client, or one documentation
    # version, in a query.
    # || Identidad de versión. El manifiesto es la declaración autoritativa (el
    # brief de procesamiento dice que la identidad del cliente vive ahí y no se
    # repite por unidad), pero un vector store filtra POR FILA: sin esto en el
    # chunk no hay forma de aislar un cliente, ni una versión de la
    # documentación, en una consulta.
    tenant_id: str = Field(
        default="default",
        description="Client this chunk belongs to, e.g. 'acme_seguros'. || Cliente al que pertenece este chunk."
    )
    doc_version: str = Field(
        default="unversioned",
        description="Documentation set version, e.g. 'DW Funtionals 2026.1'. "
        "|| Versión del set documental."
    )
    content_hash: str = Field(
        default="",
        description="SHA-256 of this chunk's `text` — the exact bytes that get embedded. "
        "Identity of the CONTENT: when it matches a previous run, the existing embedding can "
        "be reused instead of paying to regenerate it. || SHA-256 del `text` de este chunk — los "
        "bytes exactos que se embeben. Identidad del CONTENIDO: cuando coincide con una corrida "
        "anterior, el embedding existente se puede reutilizar en vez de pagar por regenerarlo."
    )
    field: str | None = Field(
        default=None,
        description="First column value of the source table row (chunk_type='table' only). "
        "|| Valor de la primera columna de la fila de tabla fuente (solo chunk_type='table').",
    )
    bullet_path: str | None = Field(
        default=None,
        description="Breadcrumb of nested bullet labels down to this chunk "
        "(chunk_type='narrative' only). || Breadcrumb de etiquetas de bullets "
        "anidados hasta este chunk (solo chunk_type='narrative').",
    )


class Chunk(BaseModel):
    """A fragment ready to be embedded.

    ``text`` includes the contextual chunk header (document + section) and is
    what gets embedded; ``metadata`` carries filterable fields that travel
    alongside the chunk but are not embedded.

    || Un fragmento listo para ser embebido. ``text`` incluye el header
    contextual del chunk (documento + sección) y es lo que se embebe;
    ``metadata`` lleva campos filtrables que viajan junto al chunk pero no
    se embeben.
    """

    chunk_id: str = Field(
        description="Format '{document_id}::{section}::{index_or_slug}'. "
        "|| Formato '{document_id}::{section}::{indice_o_slug}'."
    )
    text: str = Field(
        description="Contextual header + chunk content (what gets embedded). "
        "|| Header contextual + contenido del chunk (lo que se embebe)."
    )
    metadata: ChunkMetadata
    token_count: int = Field(
        ge=0, description="Token count of `text` (tiktoken). || Cantidad de tokens de `text` (tiktoken)."
    )
    references: list[Reference] = Field(default_factory=list)


class ChunkedDocument(BaseModel):
    """One transaction's chunks, extracted from a source file.

    A source file is NOT always one transaction: it can carry several, each as
    its own ``# `` (H1) block with its own id block — dominantly a transaction
    plus its ``_k`` key-request companion. So chunking a file yields a LIST of
    these, one per transaction found.

    || Los chunks de UNA transacción, extraídos de un archivo fuente. Un
    archivo fuente NO siempre es una transacción: puede llevar varias, cada una
    como su propio bloque ``# `` (H1) con su propio bloque de id —
    dominantemente una transacción más su acompañante ``_k`` de solicitud de
    clave. Por eso trocear un archivo produce una LISTA de estos, uno por
    transacción encontrada.
    """

    document_id: str = Field(
        description="Transaction id, from the block's own id block when present. "
        "|| Id de la transacción, del bloque de id propio del bloque cuando existe."
    )
    document_title: str = Field(description="Block title. || Título del bloque.")
    parent_transaction_code: str | None = Field(
        default=None,
        description="For a `_k` key-request transaction, the main transaction it belongs to, "
        "set only when that code is present in the same file (never guessed). "
        "|| Para una transacción `_k` de solicitud de clave, la transacción principal a la "
        "que pertenece; se completa solo cuando ese código está presente en el mismo archivo "
        "(nunca se adivina).",
    )
    is_container: bool = Field(
        default=False,
        description="True for a block with no id of its own in a file where other blocks have "
        "one: it describes the family, not one transaction. "
        "|| True para un bloque sin id propio en un archivo donde otros bloques sí lo tienen: "
        "describe la familia, no una transacción.",
    )
    transaction_type: str = Field(
        default="unknown",
        description="Type from the code's naming convention; 'unknown' when no rule matches. "
        "|| Tipo según la convención de nomenclatura del código; 'unknown' si ninguna regla matchea.",
    )
    transaction_type_reason: str | None = Field(
        default=None,
        description="Why the type is 'unknown'. Present only then, so an unclassified code says "
        "so instead of looking classified. || Por qué el tipo es 'unknown'. Presente solo en ese "
        "caso, para que un código sin clasificar lo diga en vez de parecer clasificado.",
    )
    document_kind: DocumentKind = Field(
        default="content",
        description="'index' for a chapter/navigation node. Its chunks are still produced — "
        "misclassifying content as index would silently drop business rules — so retrieval "
        "decides what to do with them. || 'index' para un nodo capítulo/navegación. Sus chunks se "
        "producen igual —clasificar contenido como índice por error descartaría reglas de negocio "
        "en silencio— así que el retrieval decide qué hacer con ellos.",
    )
    child_links: list[str] = Field(
        default_factory=list,
        description="Document codes this one links to, in order. The parent-child evidence an "
        "index document carries, cross-checkable against the WINDOWS tree. "
        "|| Códigos de documento a los que este enlaza, en orden. La evidencia padre-hijo que "
        "lleva un documento índice, cruzable contra el árbol WINDOWS.",
    )
    navigation_path: str | None = Field(
        default=None,
        description="Full path from the menu root, e.g. 'MENU > DMECAR > DMECCA > CAC020'. "
        "Present only when the WINDOWS export resolves a path to the root. "
        "|| Camino completo desde la raíz del menú. Presente solo cuando el export de WINDOWS "
        "resuelve un camino hasta la raíz.",
    )
    is_menu_node: bool | None = Field(
        default=None,
        description="From the WINDOWS tree: True = menu folder, False = executable leaf, "
        "None = absent from the tree or no export loaded. "
        "|| Del árbol WINDOWS: True = carpeta de menú, False = hoja ejecutable, "
        "None = ausente del árbol o sin export cargado.",
    )
    content_hash: str = Field(
        default="",
        description="SHA-256 of this document's normalized source text. Changes between "
        "documentation versions iff the document actually changed, so a re-ingest can skip it. "
        "|| SHA-256 del texto fuente normalizado de este documento. Cambia entre versiones de la "
        "documentación solo si el documento realmente cambió, así una reingesta puede saltearlo.",
    )
    source_revision: str | None = Field(
        default=None,
        description="Revision of this document within the documentation set, when the source "
        "carries its own revision control. || Revisión de este documento dentro del set "
        "documental, cuando la fuente lleva su propio control de revisión.",
    )
    valid_from: date | None = Field(
        default=None,
        description="Date from which this version of the document applies. Enables asking what a "
        "transaction said at a past date. || Fecha desde la cual aplica esta versión del "
        "documento. Habilita preguntar qué decía una transacción en una fecha pasada.",
    )
    chunks: list[Chunk] = Field(default_factory=list)


class CorpusManifest(BaseModel):
    """Authoritative declaration of which run produced a generated corpus.

    Mirrors the ``manifest`` of ``corpus_schema.json``, whose rule is that the
    client identity lives HERE and is not repeated per unit. The chunk metadata
    repeats ``tenant_id``/``doc_version`` anyway, for a different consumer: the
    JSON declares, the vector index filters.

    || Declaración autoritativa de qué corrida produjo un corpus generado.
    Replica el ``manifest`` de ``corpus_schema.json``, cuya regla es que la
    identidad del cliente vive ACÁ y no se repite por unidad. La metadata del
    chunk repite ``tenant_id``/``doc_version`` de todos modos, para otro
    consumidor: el JSON declara, el índice vectorial filtra.
    """

    corpus_id: str = Field(description="Id of this corpus run. || Id de esta corrida de corpus.")
    tenant_id: str = Field(description="Client identity. || Identidad del cliente.")
    doc_version: str = Field(description="Documentation set version. || Versión del set documental.")
    generated_at: datetime = Field(description="When the run produced it. || Cuándo la corrida lo produjo.")
    source_root: str = Field(description="Corpus root that was walked. || Raíz del corpus recorrida.")
    modules: list[str] = Field(default_factory=list)
    total_documents: int = Field(ge=0)
    total_chunks: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class IngestRequest(BaseModel):
    """Payload for ``POST /documents/ingest``. || Payload de ``POST /documents/ingest``."""

    filename: str = Field(
        min_length=1,
        description="Source filename, e.g. 'ca014.md'. || Nombre del archivo fuente, ej. 'ca014.md'.",
    )
    content: str = Field(
        min_length=1, description="Raw markdown of the document. || Markdown crudo del documento."
    )


class IngestStats(BaseModel):
    """Aggregate counts for observability. || Conteos agregados para observabilidad."""

    total_documents: int = Field(
        ge=0,
        description="Transactions found in the file (usually 1, more when it carries a `_k` "
        "companion). || Transacciones encontradas en el archivo (normalmente 1, más cuando "
        "lleva un acompañante `_k`).",
    )
    total_chunks: int = Field(ge=0, description="Total chunks produced. || Total de chunks producidos.")
    total_tokens: int = Field(
        ge=0, description="Sum of token_count across all chunks. || Suma de token_count de todos los chunks."
    )
    table_chunks: int = Field(
        ge=0, description="Chunks with chunk_type='table'. || Chunks con chunk_type='table'."
    )
    narrative_chunks: int = Field(
        ge=0, description="Chunks with chunk_type='narrative'. || Chunks con chunk_type='narrative'."
    )


class IngestResponse(BaseModel):
    """Response for ``POST /documents/ingest``. || Respuesta de ``POST /documents/ingest``.

    ``documents`` is a list because one source file can describe several
    transactions; a plain-single-document file yields a list of one.

    || ``documents`` es una lista porque un archivo fuente puede describir
    varias transacciones; un archivo de una sola transacción devuelve una lista
    de un elemento.
    """

    source_file: str = Field(description="Source filename as received. || Nombre del archivo fuente recibido.")
    documents: list[ChunkedDocument] = Field(
        description="One entry per transaction found in the file. "
        "|| Una entrada por transacción encontrada en el archivo."
    )
    stats: IngestStats

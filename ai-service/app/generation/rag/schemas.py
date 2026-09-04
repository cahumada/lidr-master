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

# What KIND OF SOURCE the chunk came from -- not what it is inside that source.
# `document_kind`, `chunk_type` and `transaction_type` all discriminate WITHIN a
# functional spec; none of them can say "this is a functional spec rather than a
# contract".
#
# Deliberately a plain `str` and not a `Literal`: the second source type is not
# defined yet, and a closed enum would have to be edited to add it. What matters
# now is that the column EXISTS, because it is part of the row's identity and
# adding it later means a migration plus a backfill plus regenerating the
# corpus. The chunker's wiring, by contrast, lives only in code and costs an
# afternoon whenever the second type shows up -- so that one is left alone.
# || DE QUÉ CLASE DE FUENTE viene el chunk, no qué es adentro de esa fuente.
# `document_kind`, `chunk_type` y `transaction_type` discriminan TODOS dentro de
# una especificación funcional; ninguno puede decir "esto es una especificación
# funcional y no un contrato".
#
# A propósito un `str` y no un `Literal`: el segundo tipo de fuente todavía no
# está definido, y un enum cerrado habría que editarlo para agregarlo. Lo que
# importa ahora es que la columna EXISTA, porque es parte de la identidad de la
# fila y agregarla después es una migración más un backfill más regenerar el
# corpus. El cableado del chunker, en cambio, vive solo en código y cuesta una
# tarde cuando aparezca el segundo tipo — así que a ese no se lo toca.
FUNCTIONAL_SPEC = "functional_spec"


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

    source_type: str = Field(
        default=FUNCTIONAL_SPEC,
        description="Which kind of source this came from. Today always "
        "'functional_spec'; the column exists so a second kind does not need a "
        "migration of the row's identity. || De qué clase de fuente viene. Hoy "
        "siempre 'functional_spec'; la columna existe para que una segunda clase "
        "no necesite migrar la identidad de la fila.",
    )
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
    window_type_name: str | None = Field(
        default=None,
        description="How the transaction is operated, from the WINDOWS export: puntual, "
        "secuencia or masiva, with or without a header. The name and not the code: `6` "
        "tells nobody anything. Absent when the export does not declare it. "
        "|| Cómo se opera la transacción, del export de WINDOWS: puntual, secuencia o "
        "masiva, con o sin encabezado. El nombre y no el código: `6` no le dice nada a "
        "nadie. Ausente cuando el export no lo declara.",
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
    # A statement the token cap forced apart. The chunker joins a unit that
    # leaves its statement open with what follows; when the join would exceed
    # the cap it emits them separately and links them here instead. Marking
    # beats both alternatives: forcing the join would break the cap the
    # embedding layer verifies, and dropping either side would delete a
    # business rule.
    # || Un enunciado que el techo de tokens obligó a separar. El chunker une
    # una unidad que deja el enunciado abierto con lo que sigue; cuando la
    # unión excedería el techo, los emite separados y los enlaza acá. Marcar
    # le gana a las dos alternativas: unir a la fuerza rompería el techo que
    # la capa de embeddings verifica, y descartar cualquiera de los dos lados
    # borraría una regla de negocio.
    continued_from: str | None = Field(
        default=None,
        description="chunk_id where this chunk's statement begins, when the token cap "
        "forced it apart; absent when the chunk holds a complete statement. "
        "|| chunk_id donde empieza el enunciado de este chunk, cuando el techo de "
        "tokens lo obligó a separarse; ausente cuando el chunk tiene un enunciado completo.",
    )
    continues_into: str | None = Field(
        default=None,
        description="chunk_id where this chunk's statement ends, when the token cap "
        "forced it apart; absent when the chunk holds a complete statement. "
        "|| chunk_id donde termina el enunciado de este chunk, cuando el techo de "
        "tokens lo obligó a separarse; ausente cuando el chunk tiene un enunciado completo.",
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


# --- Embedding sidecar || Sidecar de embeddings ------------------------------


class EmbeddingIndexEntry(BaseModel):
    """One row of the vector sidecar. || Una fila del sidecar de vectores.

    Row ``n`` of the ``.npy`` belongs to entry ``n`` of the index. The entry
    identifies its chunk by ``content_hash``, NOT by position: a regenerated
    corpus can add, move or drop chunks, and binding a vector to its position
    would silently repoint it at a different text.

    || La fila ``n`` del ``.npy`` corresponde a la entrada ``n`` del índice. La
    entrada identifica su chunk por ``content_hash``, NO por posición: un corpus
    regenerado puede agregar, mover o eliminar chunks, y atar un vector a su
    posición lo reapuntaría a otro texto en silencio.
    """

    chunk_id: str = Field(
        description="Locator of the chunk within its document. "
        "|| Localizador del chunk dentro de su documento."
    )
    document_id: str = Field(
        description="Transaction code the chunk belongs to. "
        "|| Código de transacción al que pertenece el chunk."
    )
    tenant_id: str = Field(description="Client the corpus belongs to. || Cliente dueño del corpus.")
    doc_version: str = Field(
        description="Documentation version of the corpus. || Versión de documentación del corpus."
    )
    content_hash: str = Field(
        description="SHA-256 of the exact text that was embedded — the identity of this row. "
        "|| SHA-256 del texto exacto que se embebió — la identidad de esta fila."
    )
    token_count: int = Field(
        ge=0, description="Tokens billed for this row. || Tokens facturados por esta fila."
    )


class EmbeddingModuleIndex(BaseModel):
    """Index file paired with one module's ``.npy``.

    || Archivo de índice apareado con el ``.npy`` de un módulo.
    """

    module: str = Field(description="Module slug. || Slug del módulo.")
    model: str = Field(description="Embedding model used. || Modelo de embeddings usado.")
    dimensions: int = Field(gt=0, description="Vector dimension. || Dimensión del vector.")
    entries: list[EmbeddingIndexEntry] = Field(
        default_factory=list,
        description="One entry per row, in row order. || Una entrada por fila, en orden de fila.",
    )


class FailedBatch(BaseModel):
    """A batch that exhausted its retries. || Un lote que agotó sus reintentos.

    The run does NOT abort: a 99.8%-embedded corpus plus a report of what is
    missing beats an aborted run. These hashes simply stay out of the index, so
    the next run picks them up by the same incremental mechanism.

    || La corrida NO aborta: un corpus 99,8% embebido más un reporte de qué
    falta es mejor que una corrida abortada. Esos hashes simplemente quedan
    fuera del índice, así que la corrida siguiente los toma por el mismo
    mecanismo incremental.
    """

    module: str = Field(description="Module the batch belonged to. || Módulo al que pertenecía el lote.")
    size: int = Field(ge=0, description="Chunks in the batch. || Chunks en el lote.")
    error: str = Field(description="Last error seen. || Último error visto.")
    chunk_ids: list[str] = Field(
        default_factory=list,
        description="Chunks left unembedded. || Chunks que quedaron sin embeber.",
    )


class EmbeddingManifest(BaseModel):
    """Authoritative record of an embedding run.

    || Registro autoritativo de una corrida de embeddings.
    """

    corpus_id: str = Field(description="Corpus that was embedded. || Corpus que se embebió.")
    tenant_id: str
    doc_version: str
    model: str
    dimensions: int = Field(gt=0)
    generated_at: str = Field(description="UTC ISO-8601 timestamp. || Timestamp UTC ISO-8601.")
    total_rows: int = Field(ge=0, description="Vectors persisted. || Vectores persistidos.")
    embedded_now: int = Field(
        ge=0, description="Vectors computed in this run. || Vectores calculados en esta corrida."
    )
    reused: int = Field(
        ge=0,
        description="Vectors reused because their content_hash was unchanged. "
        "|| Vectores reutilizados porque su content_hash no cambió.",
    )
    dropped: int = Field(
        ge=0,
        description="Rows discarded because their chunk no longer exists. "
        "|| Filas descartadas porque su chunk ya no existe.",
    )
    tokens_billed: int = Field(
        ge=0, description="Tokens sent to the model in this run. || Tokens enviados al modelo."
    )
    failed_batches: list[FailedBatch] = Field(default_factory=list)


# --- Búsqueda || Search --------------------------------------------------------


class SearchHit(BaseModel):
    """One result with its provenance. || Un resultado con su procedencia.

    Everything needed to VERIFY the answer, not just to read it: which document,
    which section, which breadcrumb, and which retrieval branch found it. A hit
    that two branches found is a different kind of answer than one a single
    branch found, and whoever reads it should be able to tell.

    || Todo lo necesario para VERIFICAR la respuesta, no solo para leerla: qué
    documento, qué sección, qué breadcrumb, y qué camino de recuperación lo
    encontró. Un hit que encontraron dos caminos es otra clase de respuesta que
    uno que encontró uno solo, y quien lee debería poder distinguirlo.
    """

    content_hash: str = Field(
        description="Row identity: SHA-256 of the embedded text. "
        "|| Identidad de la fila: SHA-256 del texto embebido."
    )
    chunk_id: str = Field(
        description="Chunk id, NOT unique on its own: 507 are shared by more than one row. "
        "|| Id del chunk, NO único por sí solo: 507 están compartidos por más de una fila."
    )
    document_id: str = Field(description="Transaction code, e.g. 'CA014'. || Código de transacción.")
    document_title: str | None = Field(
        default=None, description="Document title. || Título del documento."
    )
    section: str | None = Field(
        default=None, description="Section the chunk belongs to. || Sección a la que pertenece."
    )
    bullet_path: str | None = Field(
        default=None,
        description="Breadcrumb inside the section. || Breadcrumb dentro de la sección.",
    )
    module_code: str | None = Field(
        default=None, description="Module code, e.g. 'CA'. || Código de módulo."
    )
    document_kind: str | None = Field(
        default=None,
        description="'content' answers something; 'index' is a navigation node -- a "
        "one-line breadcrumb, not an answer. Surfaced because it now affects ranking. "
        "|| 'content' responde algo; 'index' es un nodo de navegación -- un breadcrumb de "
        "una línea, no una respuesta. Se expone porque ahora influye en el orden.",
    )
    text: str = Field(description="The chunk text. || El texto del chunk.")
    score: float = Field(description="Fused RRF score. || Puntaje RRF fusionado.")
    branches: list[str] = Field(
        default_factory=list,
        description="Which retrieval branches found it. "
        "|| Qué caminos de recuperación lo encontraron.",
    )
    ranks: dict[str, int] = Field(
        default_factory=dict,
        description="Its position within each branch that found it. "
        "|| Su posición dentro de cada camino que lo encontró.",
    )


class SearchResponse(BaseModel):
    """Response for ``GET /search``. || Respuesta de ``GET /search``.

    Carries how the answer was produced and not only what it is: the sub-queries
    a compound question was split into, whether a reranker reordered the result,
    and how many rows each branch contributed. Without that, two identical
    result lists produced by different pipelines are indistinguishable.

    || Lleva CÓMO se produjo la respuesta y no solo cuál es: en qué subconsultas
    se dividió una pregunta compuesta, si un reranker reordenó el resultado, y
    cuántas filas aportó cada camino. Sin eso, dos listas de resultados iguales
    producidas por pipelines distintos son indistinguibles.
    """

    query: str = Field(description="The query as received. || La consulta como llegó.")
    hits: list[SearchHit] = Field(description="Results, best first. || Resultados, el mejor primero.")
    count: int = Field(ge=0, description="How many hits. || Cuántos hits.")
    sub_queries: list[str] = Field(
        default_factory=list,
        description="The sub-queries a compound question was split into. Empty means it was "
        "not compound, which is the common case. || Las subconsultas en que se dividió una "
        "pregunta compuesta. Vacío significa que no era compuesta, que es el caso común.",
    )
    reranked: bool = Field(
        default=False, description="Whether a reranker reordered this. || Si un reranker lo reordenó."
    )
    branch_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Rows each branch returned, for the WHOLE query. "
        "|| Filas que devolvió cada camino, de la consulta ENTERA.",
    )
    identifier_terms: list[str] = Field(
        default_factory=list,
        description="Identifier-shaped terms detected, which is what triggers the exact branch. "
        "|| Términos con forma de identificador detectados, que es lo que dispara el camino exacto.",
    )


class SearchFacets(BaseModel):
    """Response for ``GET /search/facets``. || Respuesta de ``GET /search/facets``.

    The distinct, non-null values of the two filterable fields that actually
    have chunks loaded — neither list is a fixed enum, so a UI that wants to
    offer them as choices has to ask, not hard-code them.

    || Los valores distintos y no nulos de los dos campos filtrables que
    realmente tienen chunks cargados — ninguna de las dos listas es un enum
    fijo, así que una UI que quiera ofrecerlas como opciones tiene que
    preguntar, no escribirlas a mano.
    """

    modules: list[str] = Field(
        default_factory=list,
        description="Distinct `module_code` values present in the corpus, sorted. "
        "|| Valores distintos de `module_code` presentes en el corpus, ordenados.",
    )
    window_types: list[str] = Field(
        default_factory=list,
        description="Distinct `window_type_name` values present in the corpus, sorted. "
        "|| Valores distintos de `window_type_name` presentes en el corpus, ordenados.",
    )


# --- Answer generation || Generación de respuestas ---------------------------


def search_hits_from_chunks(chunks: list) -> list[SearchHit]:
    """Map retrieved chunks to the public ``SearchHit`` contract.

    Shared by ``GET /search`` and ``POST /answer`` so the two endpoints cannot
    drift on what a citation is.

    || Mapea chunks recuperados al contrato público ``SearchHit``. Lo
    comparten ``GET /search`` y ``POST /answer`` para que los dos endpoints
    no puedan divergir en qué es una cita.
    """
    return [
        SearchHit(
            content_hash=chunk.content_hash,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            section=chunk.section,
            bullet_path=chunk.bullet_path,
            module_code=chunk.module_code,
            document_kind=chunk.document_kind,
            text=chunk.text,
            score=chunk.score,
            branches=chunk.branches,
            ranks=chunk.ranks,
        )
        for chunk in chunks
    ]


class AnswerRequest(BaseModel):
    """Payload for ``POST /answer``. || Payload de ``POST /answer``.

    The retrieval knobs default to the measured pipeline — the same defaults
    as ``GET /search`` — so a caller that only sends ``question`` gets the
    configuration that scored ``p@10`` 0.171, not a cheaper unmeasured one.

    ``question`` carries ``min_length=2``, the same rule ``Query(min_length=2)``
    already enforces on ``/search``. That is the input guardrail; it is not
    restated in a second function.

    || Los knobs de recuperación defaultan al pipeline medido —los mismos que
    ``GET /search``— así un llamador que solo manda ``question`` obtiene la
    configuración que midió ``p@10`` 0,171, no una más barata sin medir.
    ``question`` lleva ``min_length=2``, la misma regla que
    ``Query(min_length=2)`` ya impone en ``/search``. Ese es el guardrail de
    entrada; no se reitera en una segunda función.
    """

    question: str = Field(
        min_length=2,
        description="The question, in natural language or a transaction code. "
        "|| La pregunta, en lenguaje natural o un código de transacción.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="How many chunks enter the prompt. || Cuántos chunks entran al prompt.",
    )
    max_per_document: int | None = Field(
        default=1,
        ge=1,
        description="Cap of chunks per document. Default 1, the measured search default. "
        "|| Tope de chunks por documento. Default 1, el default medido de la búsqueda.",
    )
    module_code: list[str] | None = Field(
        default=None,
        description="Restrict to one or more modules, e.g. ['CA', 'DF']. "
        "|| Restringir a uno o varios módulos, ej. ['CA', 'DF'].",
    )
    window_type_name: list[str] | None = Field(
        default=None,
        description="Restrict by one or more window types. "
        "|| Restringir por uno o varios tipos de ventana.",
    )
    lexical: bool = Field(
        default=False,
        description="Add the full-text branch. Off by default: the measured search default. "
        "|| Agregar el camino full-text. Apagado por default: el default medido de la búsqueda.",
    )
    split: bool = Field(
        default=True,
        description="Split a compound question and add what the parts find. "
        "|| Dividir una pregunta compuesta y agregar lo que encuentran las partes.",
    )
    rerank: bool = Field(
        default=True,
        description="Reorder the candidate set before building the prompt. "
        "|| Reordenar el candidato antes de armar el prompt.",
    )
    profile_id: str | None = Field(
        default=None,
        description="Named synthesizer profile for this run. Absent = the default. "
        "|| Perfil nombrado del sintetizador para esta corrida. Ausente = el default.",
    )


class AnswerResponse(BaseModel):
    """Response for ``POST /answer``. || Respuesta de ``POST /answer``.

    ``citations`` is the retrieved hits, not the markers the model wrote.
    Verifying a citation means looking at this list. ``grounded`` says
    whether the prose invented a ``document_id`` that is not in it.

    || ``citations`` son los hits recuperados, no los marcadores que escribió
    el modelo. Verificar una cita es mirar esta lista. ``grounded`` dice si
    la prosa inventó un ``document_id`` que no está en ella.
    """

    question: str = Field(
        description="The question as received. || La pregunta como llegó.",
    )
    answer: str = Field(
        description="The generated answer. || La respuesta generada.",
    )
    citations: list[SearchHit] = Field(
        description="The chunks the answer was generated from — the verifiable provenance. "
        "|| Los chunks a partir de los cuales se generó la respuesta — la procedencia verificable.",
    )
    grounded: bool = Field(
        description="False when the prose cites a document_id that is not in `citations`. "
        "|| False cuando la prosa cita un document_id que no está en `citations`.",
    )

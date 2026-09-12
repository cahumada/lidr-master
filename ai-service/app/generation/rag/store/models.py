"""The tables: one for the chunks, one for what version is live.

The course (``session_16``) has one chunk table per source kind -- budgets,
transcripts, technical docs -- because it ingests three. This project ingests
one: functional specifications. A mixin with a single implementation is the
same empty abstraction already turned down in ``chunking/base.py``.

The course also keeps its filterable metadata in a JSONB column with a GIN
index, which is right when the metadata is open-ended. Ours is not:
:class:`~app.generation.rag.schemas.ChunkMetadata` has fixed fields and they are
exactly what gets filtered. In columns they can be indexed in pairs, the planner
has real statistics, and a mistyped field name is a SQL error instead of a
filter that silently matches nothing.

|| Las tablas: una para los chunks, otra para qué versión está vigente.

El curso (``session_16``) tiene una tabla de chunks por clase de fuente porque
ingiere tres. Este proyecto ingiere una: especificaciones funcionales. Un mixin
con una sola implementación es la misma abstracción vacía que ya se descartó en
``chunking/base.py``.

El curso además guarda su metadata filtrable en una columna JSONB con índice
GIN, que es lo correcto cuando la metadata es abierta. La nuestra no lo es:
:class:`~app.generation.rag.schemas.ChunkMetadata` tiene campos fijos y son
justamente los que se filtran. En columnas se indexan de a pares, el planner
tiene estadísticas reales y un nombre de campo mal escrito es un error de SQL en
vez de un filtro que no matchea nada en silencio.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Computed,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.foundation.persistence.database import Base
from app.generation.rag.schemas import FUNCTIONAL_SPEC

# Hard-coded rather than read from Settings: the column type is baked into the
# schema by a migration, so it cannot follow a runtime setting. It must match
# `Settings.EMBEDDING_DIMENSIONS`, and a test asserts that it does.
# || Fijo en vez de leído de Settings: el tipo de columna queda grabado en el
# esquema por una migración, así que no puede seguir a un setting de runtime.
# Tiene que coincidir con `Settings.EMBEDDING_DIMENSIONS`, y hay un test que lo
# verifica.
EMBEDDING_DIMENSIONS = 1536

# `vector` and not `halfvec`: pgvector's HNSW index takes up to 2000 dimensions
# with `vector` and up to 4000 with `halfvec`, and the course casts to halfvec
# for that headroom. 1536 fits comfortably, and halfvec is half precision --
# the 175 MB saved buys nothing here. This is the lever if the dimension ever
# grows.
# || `vector` y no `halfvec`: el índice HNSW de pgvector tolera hasta 2000
# dimensiones con `vector` y hasta 4000 con `halfvec`, y el curso castea a
# halfvec por ese margen. 1536 entra holgado, y halfvec es media precisión — los
# 175 MB que ahorra no compran nada acá. Esta es la palanca si algún día sube la
# dimensión.
_FTS_REGCONFIG = get_settings().FTS_REGCONFIG


class ChunkRow(Base):
    """One embedded chunk of the corpus. || Un chunk embebido del corpus."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # --- Identity || Identidad ----------------------------------------------

    # The row's identity is (tenant, version, content_hash), NOT chunk_id.
    # chunk_id shifts when the corpus is regenerated; binding identity to a
    # locator would silently repoint rows at a different text. This is also
    # what makes the load idempotent.
    # || La identidad de la fila es (tenant, versión, content_hash), NO
    # chunk_id. El chunk_id se corre cuando el corpus se regenera; atar la
    # identidad a un localizador reapuntaría filas a otro texto en silencio.
    # Es además lo que hace idempotente la carga.
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_version: Mapped[str] = mapped_column(String(128), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Part of the row's identity, not a metadata field. Today every row says
    # `functional_spec`, and the point is that a second kind of source does not
    # need to migrate the unique key of 57101 rows to exist.
    #
    # Note what this does NOT fix: cross-document collisions were already
    # impossible, because the hashed text carries the contextual header
    # `[Documento: CA014 - <titulo>]`. Measured on the corpus: 3017 hashes
    # repeat, 0 of them across different `document_id`. This is insurance for a
    # future source type that may not carry such a header, and -- the real
    # reason -- it is what makes a mixed corpus filterable at all.
    # || Parte de la identidad de la fila, no un campo de metadata. Hoy todas
    # dicen `functional_spec`, y el punto es que una segunda clase de fuente no
    # necesite migrar la clave unica de 57101 filas para existir.
    #
    # Ojo con lo que esto NO arregla: las colisiones entre documentos ya eran
    # imposibles, porque el texto hasheado lleva el header contextual
    # `[Documento: CA014 - <titulo>]`. Medido sobre el corpus: 3017 hashes se
    # repiten, 0 entre `document_id` distintos. Esto es seguro para un tipo de
    # fuente futuro que tal vez no lleve ese header y, la razon de verdad, es lo
    # que hace filtrable un corpus mixto.
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=FUNCTIONAL_SPEC
    )

    # Traceability back to the source document, not identity.
    # || Trazabilidad al documento fuente, no identidad.
    chunk_id: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False)
    document_title: Mapped[str | None] = mapped_column(Text)

    # --- What gets embedded and searched || Lo que se embebe y se busca ------

    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # STORED and generated by the database, not written by the loader and not
    # maintained by a trigger: that is what makes it impossible for the lexemes
    # to drift out of sync with the text.
    # || STORED y generada por la base, no escrita por el cargador ni mantenida
    # por un trigger: es lo que hace imposible que los lexemas se
    # desincronicen del texto.
    content_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(f"to_tsvector('{_FTS_REGCONFIG}', text)", persisted=True),
        nullable=False,
    )

    # --- Filterable metadata || Metadata filtrable ---------------------------

    chunk_type: Mapped[str] = mapped_column(String(32), nullable=False)
    section: Mapped[str | None] = mapped_column(Text)
    bullet_path: Mapped[str | None] = mapped_column(Text)
    field: Mapped[str | None] = mapped_column(Text)
    transaction_type: Mapped[str | None] = mapped_column(String(32))
    document_kind: Mapped[str | None] = mapped_column(String(32))
    module_code: Mapped[str | None] = mapped_column(String(32))
    module_name: Mapped[str | None] = mapped_column(Text)
    submodule_code: Mapped[str | None] = mapped_column(String(32))
    submodule_name: Mapped[str | None] = mapped_column(Text)
    # How the transaction is operated, DECLARED by the WINDOWS export: puntual,
    # secuencia or masiva, with or without a header. A filter, not a read.
    # || Cómo se opera la transacción, DECLARADO por el export de WINDOWS:
    # puntual, secuencia o masiva, con o sin encabezado. Un filtro, no una
    # lectura.
    window_type_name: Mapped[str | None] = mapped_column(String(48))
    # Declared record status from `TABLE26` (`SSTATREGT`). Not indexed: no filter
    # in this change.
    # || Estado declarado del registro según `TABLE26` (`SSTATREGT`). Sin índice:
    # no hay filtro en este change.
    window_status: Mapped[str | None] = mapped_column(String(48))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "doc_version",
            "source_type",
            "content_hash",
            name="uq_chunks_tenant_version_hash",
        ),
        # The operator class MUST match the operator the query uses (`<=>`).
        # When they disagree Postgres does not fail -- it ignores the index and
        # scans sequentially, which is an invisible degradation.
        # || El operator class DEBE coincidir con el operador que usa la
        # consulta (`<=>`). Cuando no coinciden Postgres no falla: ignora el
        # índice y hace scan secuencial, que es una degradación invisible.
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={
                "m": get_settings().HNSW_M,
                "ef_construction": get_settings().HNSW_EF_CONSTRUCTION,
            },
        ),
        Index("ix_chunks_content_tsv", "content_tsv", postgresql_using="gin"),
        # The pre-filter every query carries, so it leads the composite index.
        # || El pre-filtro que lleva toda consulta, así que encabeza el índice
        # compuesto.
        Index("ix_chunks_tenant_version", "tenant_id", "doc_version"),
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_module_code", "module_code"),
        Index("ix_chunks_window_type", "tenant_id", "doc_version", "window_type_name"),
        Index("ix_chunks_source_type", "tenant_id", "doc_version", "source_type"),
    )


class CorpusVersionRow(Base):
    """Which documentation version is live for a client.

    || Qué versión de la documentación está vigente para un cliente.
    """

    __tablename__ = "corpus_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_version: Mapped[str] = mapped_column(String(128), nullable=False)
    corpus_id: Mapped[str | None] = mapped_column(String(64))

    # 'loaded' | 'active' | 'retired'. Kept as text rather than an enum type so
    # adding a state is a data change, not a migration on a Postgres type.
    # || 'loaded' | 'active' | 'retired'. Texto en vez de un tipo enum para que
    # agregar un estado sea un cambio de datos y no una migración sobre un tipo
    # de Postgres.
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="loaded")

    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Deliberately NO foreign key to `chunks`: a version can be declared before
    # its rows finish loading, and a half-loaded version must not be able to
    # activate itself. Activation is explicit.
    # || A propósito SIN foreign key contra `chunks`: una versión puede
    # declararse antes de terminar de cargar sus filas, y una versión a medias
    # no debe poder activarse sola. Activar es explícito.
    __table_args__ = (
        UniqueConstraint("tenant_id", "doc_version", name="uq_corpus_versions_tenant_version"),
        # At most one active version per client, enforced by the database. The
        # same rule held only in application code breaks under two concurrent
        # processes.
        # || A lo sumo una versión activa por cliente, garantizado por la base.
        # La misma regla sostenida solo en el código de la aplicación se rompe
        # con dos procesos concurrentes.
        Index(
            "uq_corpus_versions_one_active_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where="status = 'active'",
        ),
    )


class ProcessMapEdgeRow(Base):
    """One edge of the process map. || Una arista del mapa de procesos.

    The map lives in two shapes because it has two consumers: the CAG context
    is preloaded whole and is text, while retrieval needs to ask "what
    references `CA014`?" for one query -- and loading the whole graph for that
    would be absurd. Same data, each in the shape its consumer needs.

    || El mapa vive en dos formas porque tiene dos consumidores: el contexto del
    CAG se precarga entero y es texto, mientras la recuperación necesita
    preguntar "¿qué referencia a `CA014`?" para una consulta — y cargar el grafo
    entero para eso sería absurdo. El mismo dato, cada uno en la forma que su
    consumidor necesita.
    """

    __tablename__ = "process_map_edges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_version: Mapped[str] = mapped_column(String(128), nullable=False)

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(64), nullable=False)

    # 'menu_parent' | 'requires' | 'references'. The three never collapse: the
    # biggest emitters of `references` are index documents, so a consumer that
    # read them as precedence would conclude LIFE_INDEX has 130 process
    # dependencies.
    # || Las tres nunca se colapsan: los mayores emisores de `references` son
    # documentos índice, así que un consumidor que las leyera como precedencia
    # concluiría que LIFE_INDEX tiene 130 dependencias de proceso.
    edge_type: Mapped[str] = mapped_column(String(16), nullable=False)

    # Which source produced it, so any edge can be audited back.
    # || Qué fuente la produjo, así cualquier arista se puede auditar.
    origin: Mapped[str] = mapped_column(String(32), nullable=False)

    # The sentence that justified a `requires` edge.
    # || La oración que justificó una arista `requires`.
    evidence: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "doc_version", "source", "target", "edge_type",
            name="uq_process_map_edges_identity",
        ),
        # Indexed on BOTH ends: retrieval expands in either direction -- what
        # does this reference, and what references this.
        # || Indexada en las DOS puntas: la recuperación expande en cualquier
        # dirección — qué referencia esto, y qué lo referencia a esto.
        Index("ix_process_map_edges_source", "tenant_id", "doc_version", "source", "edge_type"),
        Index("ix_process_map_edges_target", "tenant_id", "doc_version", "target", "edge_type"),
    )


class TransactionTableEdge(Base):
    """One table a transaction touches, as Oracle's dependency graph declares it.

    Keyed by the MIRROR's ``run_id`` and not by ``doc_version``, unlike
    :class:`ProcessMapEdge`. What this row asserts is what Oracle declared in
    one extraction run: activating another run has to be able to bring other
    edges. The corpus version only decides which codes were looked up.

    Materialized by ``scripts/build_transaction_tables.py`` instead of resolved
    per request, for a reason that is about correctness and not only cost: the
    first hop matches a ``document_id`` inside a routine name, and 184 codes are
    substrings of another code. Disambiguating needs the whole universe of
    codes, which a request does not have -- ``CA013`` would arrive without
    ``CA013A`` in sight and walk off with ``INSPOSTCA013A``.

    || Una tabla que toca una transacción, como la declara el grafo de
    dependencias de Oracle. Va por el ``run_id`` del MIRROR y no por
    ``doc_version``: lo que la fila afirma es lo que Oracle declaró en esa
    corrida. Se materializa en batch porque desambiguar el salto por nombre
    necesita el universo entero de códigos, que en un request no está.
    """

    __tablename__ = "transaction_table_edges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # The mirror's coordinates, not the corpus'. || Las coordenadas del mirror.
    tenant: Mapped[str] = mapped_column(String(100), nullable=False)
    env: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # `document_id` of the functional spec == `WINDOWS.SCODISPL`.
    # || `document_id` de la especificación == `WINDOWS.SCODISPL`.
    transaction_code: Mapped[str] = mapped_column(String(64), nullable=False)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # 'reference' | 'historical' | 'message' | 'validation' | 'unknown'.
    # A closed vocabulary with no catch-all: `unknown` carries its reason rather
    # than being replaced by a default, same rule as the code taxonomy.
    #
    # There is deliberately no 'core'. Measured against the four transactions
    # the repo owner annotated, no declared signal separates the table the
    # analyst calls core from the rest, and the one the plan proposed -- a low
    # global fan-in -- runs backwards: COVER (1,037), CLIENT (1,925) and
    # CERTIFICAT (1,989) are the annotated ones, while NOPAYROLL (44) and
    # CUR_ALLOW (30) are not. A central entity is touched by everything BECAUSE
    # it is central. Asserting `core` from that would be an inference dressed as
    # a declared fact.
    # || No hay 'core' a propósito: ninguna señal declarada lo separa, y el
    # fan-in bajo que proponía el plan corre al revés.
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    role_reason: Mapped[str] = mapped_column(Text, nullable=False)

    # The routines the dependency came from, comma-separated and ordered. This
    # is the provenance: a table asserted without saying why it entered is the
    # same defect as a chunk without its document.
    # || Las rutinas de las que salió la dependencia. Es la procedencia.
    via_routines: Mapped[str] = mapped_column(Text, nullable=False)

    # How many routines in the WHOLE run depend on this table. CERTIFICAT has
    # 1,910: that a transaction touches it does not inform. Stored so the role
    # decision can be revisited without rebuilding the edges.
    # || Cuántas rutinas de TODA la corrida dependen de esta tabla.
    fan_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # How many of THIS transaction's routines reach the table, over how many it
    # has. Two declared counts, not a fitted score -- coverage is the ordering
    # signal precisely because it needs no threshold to mean something.
    # || Cuántas rutinas DE ESTA transacción llegan a la tabla, sobre cuántas
    # tiene. Dos conteos declarados, no un puntaje calibrado.
    routine_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    routine_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Which path produced it, so any edge can be audited back. Today only
    # 'dependency_graph'; the field exists because §5.2 and §5.3 of the domain
    # note describe other paths that would arrive as indicios, not facts.
    # || Qué camino la produjo, para poder auditarla.
    origin: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant", "env", "run_id", "transaction_code", "table_name",
            name="uq_transaction_table_edges_identity",
        ),
        # One index, on the code: the read is always "what does this code
        # touch?". The reverse question -- who touches this table -- is not a
        # use case yet, and an index nobody queries is a write cost.
        # || Un solo índice, por código: la lectura es siempre «¿qué toca este
        # código?». La pregunta inversa todavía no es un caso de uso.
        Index(
            "ix_transaction_table_edges_code",
            "tenant", "env", "run_id", "transaction_code",
        ),
    )


class TransactionTableBuild(Base):
    """One row per run whose edges were built: the answer to "does this run have edges?".

    Without it, that question is a ``COUNT`` over ``transaction_table_edges`` on
    every request, and -- worse -- zero edges would be indistinguishable from a
    build that ran and found nothing. A run with a row here and no edges built
    fine; a run with no row never built.

    || Una fila por corrida cuyas aristas se construyeron. Sin ella, cero
    aristas sería indistinguible de un batch que corrió y no encontró nada.
    """

    __tablename__ = "transaction_table_builds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    tenant: Mapped[str] = mapped_column(String(100), nullable=False)
    env: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # What the build produced, so the console can show it without counting.
    # || Lo que produjo el batch, para que la consola no tenga que contar.
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    code_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Which corpus version supplied the codes. The edges are keyed by the
    # mirror run; this records which document set was looked up against it.
    # || Qué versión del corpus aportó los códigos.
    doc_version: Mapped[str] = mapped_column(String(128), nullable=False)

    built_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant", "env", "run_id",
            name="uq_transaction_table_builds_identity",
        ),
    )

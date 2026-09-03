"""Store tests that need no database.

The SQL that gets built, the row that gets joined, the vector that gets
formatted — all verifiable without Postgres, and so they run on every `pytest`.

|| Tests del store que no necesitan base. El SQL que se construye, la fila que
se une, el vector que se formatea — todo verificable sin Postgres, así que
corren en cada `pytest`.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest
from sqlalchemy.dialects import postgresql

from app.config import get_settings
from app.foundation.persistence.database import to_async_url, to_sync_url
from app.generation.rag.embedding.embedder import HashEmbedder
from app.generation.rag.embedding.sidecar import empty_index, write_sidecar
from app.generation.rag.store.loader import COPY_COLUMNS, format_vector, iter_rows
from app.generation.rag.store.models import EMBEDDING_DIMENSIONS, ChunkRow, CorpusVersionRow
from app.generation.rag.store.repository import (
    SearchFilters,
    SearchHit,
    build_search_statement,
)

DIMS = 8


def compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


# --- One URL, two stacks --------------------------------------------------


def test_the_driver_token_is_swapped_both_ways():
    """A second URL would be one more thing that can point somewhere else."""
    url = "postgresql+psycopg://u:p@h:5432/d"
    assert to_async_url(url) == "postgresql+asyncpg://u:p@h:5432/d"
    assert to_sync_url(to_async_url(url)) == url


def test_a_driverless_url_gets_one():
    assert to_async_url("postgresql://u:p@h/d") == "postgresql+asyncpg://u:p@h/d"
    assert to_sync_url("postgresql://u:p@h/d") == "postgresql+psycopg://u:p@h/d"


def test_rewriting_is_idempotent():
    once = to_async_url("postgresql://u:p@h/d")
    assert to_async_url(once) == once


# --- The schema ------------------------------------------------------------


def test_the_column_dimension_matches_the_embedding_setting():
    """The column type is baked into the schema by a migration, so it cannot
    follow a runtime setting. If they drift, every load fails at COPY time."""
    assert EMBEDDING_DIMENSIONS == get_settings().EMBEDDING_DIMENSIONS


def test_the_row_identity_is_tenant_version_and_hash():
    constraints = {c.name for c in ChunkRow.__table__.constraints}
    assert "uq_chunks_tenant_version_hash" in constraints


def test_the_vector_index_uses_the_cosine_operator_class():
    """When the operator class and the query's operator disagree Postgres does
    not fail -- it ignores the index."""
    index = next(i for i in ChunkRow.__table__.indexes if i.name == "ix_chunks_embedding_hnsw")
    assert index.dialect_options["postgresql"]["using"] == "hnsw"
    assert index.dialect_options["postgresql"]["ops"] == {"embedding": "vector_cosine_ops"}


def test_the_full_text_column_is_generated_in_spanish():
    """Generated and STORED, so it cannot drift out of sync with the text; and
    Spanish, because with the English stemmer `pólizas` and `póliza` do not
    collapse."""
    column = ChunkRow.__table__.c.content_tsv
    assert column.computed is not None
    assert column.computed.persisted is True
    assert "spanish" in str(column.computed.sqltext)


def test_only_one_version_can_be_active_per_tenant():
    index = next(
        i
        for i in CorpusVersionRow.__table__.indexes
        if i.name == "uq_corpus_versions_one_active_per_tenant"
    )
    assert index.unique is True
    assert "active" in str(index.dialect_options["postgresql"]["where"])


# --- The search statement ---------------------------------------------------


def test_the_search_uses_cosine_distance_and_orders_by_it():
    sql = compiled(build_search_statement([0.1] * DIMS, SearchFilters("acme", "v1"), limit=5))
    assert "<=>" in sql
    assert "ORDER BY distance" in sql
    assert "LIMIT" in sql


def test_tenant_and_version_are_always_predicates():
    """A query that forgot them would rank one client's chunks against another's."""
    sql = compiled(build_search_statement([0.1] * DIMS, SearchFilters("acme", "v1"), limit=5))
    assert "chunks.tenant_id = " in sql
    assert "chunks.doc_version = " in sql


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("module_code", {"module_code": "DMECAR"}),
        ("transaction_type", {"transaction_type": "query"}),
        ("document_kind", {"document_kind": "content"}),
        ("chunk_type", {"chunk_type": "table"}),
        ("document_id", {"document_id": "CA014"}),
    ],
)
def test_every_optional_filter_becomes_a_predicate(field_name, kwargs):
    """As predicates and not as a filter over the results: in the WHERE clause
    the index can narrow the candidate set."""
    sql = compiled(
        build_search_statement([0.1] * DIMS, SearchFilters("acme", "v1", **kwargs), limit=5)
    )
    assert f"chunks.{field_name} = " in sql


def test_an_absent_filter_adds_no_predicate():
    sql = compiled(build_search_statement([0.1] * DIMS, SearchFilters("acme", "v1"), limit=5))
    assert "chunks.module_code = " not in sql


def test_similarity_is_the_complement_of_distance():
    hit = SearchHit("h", "c", "CA014", None, None, None, None, "texto", distance=0.25)
    assert hit.similarity == pytest.approx(0.75)


# --- Loading ----------------------------------------------------------------


def test_the_vector_is_formatted_the_way_pgvector_reads_it():
    assert format_vector(np.array([0.5, -0.25], dtype=np.float32)) == "[0.5,-0.25]"


def test_the_copy_columns_match_the_table():
    """COPY writes positionally; a column here that is not on the table, or the
    other way round, misaligns every row."""
    table_columns = set(ChunkRow.__table__.c.keys())
    assert set(COPY_COLUMNS) <= table_columns
    # Everything not copied is either generated or defaulted by the database.
    # || Todo lo que no se copia lo genera o lo completa la base.
    assert table_columns - set(COPY_COLUMNS) == {"id", "content_tsv", "created_at"}


def _write_corpus(tmp_path, texts: list[str]) -> tuple:
    chunks_dir = tmp_path / "chunks"
    embeddings_dir = tmp_path / "embeddings"
    chunks_dir.mkdir()

    def chunk(text: str, index: int) -> dict:
        return {
            "chunk_id": f"CA014::campos::{index}",
            "text": text,
            "token_count": 10,
            "metadata": {
                "tenant_id": "acme",
                "doc_version": "v1",
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "chunk_type": "table",
                "section": "Campos",
                "module_code": "DMECAR",
                "window_type_name": "Masivo con encabezado",
            },
        }

    payload = {
        "module": "policies",
        "documents": [
            {
                "document_id": "CA014",
                "document_title": "Datos de la póliza",
                "chunks": [chunk(t, i) for i, t in enumerate(texts)],
            }
        ],
    }
    (chunks_dir / "policies.json").write_text(json.dumps(payload), encoding="utf-8")
    return chunks_dir, embeddings_dir, payload


def test_rows_are_joined_to_their_vector_by_content_hash(tmp_path):
    chunks_dir, embeddings_dir, payload = _write_corpus(tmp_path, ["alta", "baja"])
    embedder = HashEmbedder(DIMS)
    chunks = payload["documents"][0]["chunks"]
    index = empty_index("policies", embedder.model, DIMS)
    from app.generation.rag.schemas import EmbeddingIndexEntry

    index.entries = [
        EmbeddingIndexEntry(
            chunk_id=c["chunk_id"],
            document_id="CA014",
            tenant_id="acme",
            doc_version="v1",
            content_hash=c["metadata"]["content_hash"],
            token_count=10,
        )
        for c in chunks
    ]
    vectors = np.array(embedder.embed([c["text"] for c in chunks]), dtype=np.float32)
    write_sidecar(embeddings_dir, "policies", vectors, index)

    module, rows, without_vector = iter_rows(chunks_dir / "policies.json", embeddings_dir)

    assert module == "policies"
    assert len(rows) == 2
    assert without_vector == []
    # Column 7 is `embedding`; it must carry the sidecar's vector, not a new one.
    # || La columna 7 es `embedding`; tiene que llevar el vector del sidecar.
    assert rows[0][COPY_COLUMNS.index("embedding")] == format_vector(vectors[0])
    assert rows[0][COPY_COLUMNS.index("document_title")] == "Datos de la póliza"


def test_a_chunk_with_no_vector_is_reported_not_invented(tmp_path):
    """A zero vector would index the chunk where nothing ever matches -- the
    silent failure the embedding layer already refuses."""
    chunks_dir, embeddings_dir, payload = _write_corpus(tmp_path, ["alta", "sin vector"])
    embedder = HashEmbedder(DIMS)
    first = payload["documents"][0]["chunks"][0]
    from app.generation.rag.schemas import EmbeddingIndexEntry

    index = empty_index("policies", embedder.model, DIMS)
    index.entries = [
        EmbeddingIndexEntry(
            chunk_id=first["chunk_id"],
            document_id="CA014",
            tenant_id="acme",
            doc_version="v1",
            content_hash=first["metadata"]["content_hash"],
            token_count=10,
        )
    ]
    write_sidecar(
        embeddings_dir,
        "policies",
        np.array(embedder.embed([first["text"]]), dtype=np.float32),
        index,
    )

    _, rows, without_vector = iter_rows(chunks_dir / "policies.json", embeddings_dir)

    assert len(rows) == 1
    assert without_vector == ["CA014::campos::1"]


# --- source_type: la puerta abierta a otros tipos de fuente --------------------


def test_the_row_identity_includes_the_source_type():
    """La identidad de una fila es cliente + versión + CLASE DE FUENTE + texto.

    El tipo de fuente está en la clave única a propósito, aunque hoy haya un
    solo valor: agregarlo después sería migrar la clave de 57.101 filas. Lo que
    NO arregla es colisiones entre documentos, que ya eran imposibles porque el
    texto hasheado lleva el header `[Documento: CA014 - <título>]` — medido, 0
    de los 3.017 hashes repetidos del corpus cruzan `document_id`.
    """
    unique = next(
        c for c in ChunkRow.__table__.constraints if c.name == "uq_chunks_tenant_version_hash"
    )
    assert tuple(column.name for column in unique.columns) == (
        "tenant_id",
        "doc_version",
        "source_type",
        "content_hash",
    )


def test_the_source_type_is_not_a_metadata_column():
    """Es identidad, no metadata: un conflicto NO lo reescribe.

    Si estuviera en `_METADATA_COLUMNS`, una carga podría cambiarle la clase de
    fuente a una fila existente, que es justamente lo que la clave única
    previene.
    """
    from app.generation.rag.store.loader import _METADATA_COLUMNS

    assert "source_type" not in _METADATA_COLUMNS


def test_the_source_type_travels_in_the_copy_row():
    from app.generation.rag.store.loader import COPY_COLUMNS

    assert "source_type" in COPY_COLUMNS


def test_searching_every_source_type_is_the_default():
    """`None` es todas. Filtrar al único valor que existe sería un no-op con
    aspecto de decisión."""
    assert SearchFilters("acme", "v1").source_type is None


def test_the_source_type_narrows_the_search():
    sql = compiled(
        build_search_statement(
            [0.1] * DIMS,
            SearchFilters("acme", "v1", source_type="functional_spec"),
            limit=5,
        )
    )
    assert "chunks.source_type = " in sql

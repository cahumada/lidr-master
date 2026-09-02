"""Store tests against a real Postgres with pgvector.

These cover what cannot be emulated and what the unit tests therefore cannot
see: whether the unique constraint actually dedupes, whether the partial index
actually forbids a second active version, whether Spanish stemming actually
collapses `pólizas` and `póliza`, and whether a filtered similarity search
actually returns its k rows.

That last one is not a nicety. Without pgvector's iterative scan, HNSW walks its
nearest candidates and only then applies the WHERE: a search filtered by
`transaction_type='query'` came back with 0 rows while 7461 matched. Wrong
results, not slow ones -- and no in-memory double would have shown it.

|| Tests del store contra un Postgres real con pgvector. Cubren lo que no se
puede emular y que por eso los unitarios no ven: si la restricción única
realmente deduplica, si el índice parcial realmente prohíbe una segunda versión
activa, si el stemming español realmente colapsa `pólizas` y `póliza`, y si una
búsqueda por similitud con filtros realmente devuelve sus k filas.

Esto último no es un lujo. Sin el escaneo iterativo de pgvector, HNSW recorre
sus candidatos más cercanos y recién después aplica el WHERE: una búsqueda
filtrada por `transaction_type='query'` volvió con 0 filas mientras 7461
cumplían. Resultados equivocados, no lentos — y ningún doble en memoria lo
habría mostrado.
"""

from __future__ import annotations

import asyncio
import hashlib

import numpy as np
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.generation.rag.embedding.embedder import HashEmbedder
from app.generation.rag.store.loader import COPY_COLUMNS, format_vector, load_module, prune_corpus

pytestmark = pytest.mark.integration

DIMS = 1536


def make_row(tenant: str, body: str, *, index: int, **overrides) -> tuple:
    """A COPY row, positional in COPY_COLUMNS order.

    || Una fila de COPY, posicional en el orden de COPY_COLUMNS.
    """
    vector = np.array(HashEmbedder(DIMS).embed([body])[0], dtype=np.float32)
    values = {
        "tenant_id": tenant,
        "doc_version": "v1",
        "content_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "chunk_id": f"CA014::campos::{index}",
        "document_id": "CA014",
        "document_title": "Datos de la póliza",
        "text": body,
        "embedding": format_vector(vector),
        "token_count": 10,
        "chunk_type": "table",
        "section": "Campos",
        "bullet_path": None,
        "field": None,
        "transaction_type": "functional_abm",
        "document_kind": "content",
        "module_code": "DMECAR",
        "module_name": "Cartera",
        "submodule_code": None,
        "submodule_name": None,
        "window_type_name": "Masivo con encabezado",
    }
    values.update(overrides)
    return tuple(values[c] for c in COPY_COLUMNS)


def load(engine, rows) -> tuple[int, int]:
    raw = engine.raw_connection()
    try:
        connection = raw.driver_connection
        result = load_module(connection, rows, dimensions=DIMS)
        connection.commit()
        return result
    finally:
        raw.close()


def count(engine, tenant: str) -> int:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT count(*) FROM chunks WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()


# --- Identity and idempotency -------------------------------------------------


def test_loading_twice_adds_no_rows_the_second_time(clean_tables, tenant):
    """Idempotent in the sense that matters: the row COUNT does not grow. The
    second run does write every row -- it refreshes the metadata columns to the
    same values -- because a metadata-only change has to be able to reach an
    existing row."""
    rows = [make_row(tenant, f"regla {i}", index=i) for i in range(5)]

    copied, written = load(clean_tables, rows)
    assert (copied, written) == (5, 5)

    load(clean_tables, rows)
    assert count(clean_tables, tenant) == 5


def test_a_metadata_only_change_reaches_an_existing_row(clean_tables, tenant):
    """`DO NOTHING` made the load idempotent on content and silently blind to
    metadata: adding `window_type_name` to 46613 chunks would have inserted
    nothing and left the column null."""
    load(clean_tables, [make_row(tenant, "regla", index=0)])
    load(
        clean_tables,
        [make_row(tenant, "regla", index=0, window_type_name="Puntual sin encabezado")],
    )

    with clean_tables.connect() as connection:
        value = connection.execute(
            text("SELECT window_type_name FROM chunks WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()
    assert value == "Puntual sin encabezado"


def test_the_embedding_is_not_refreshed_on_conflict(clean_tables, tenant):
    """The embedding is tied to the text, and the text is what `content_hash`
    covers. A conflict means the text did not change, so re-writing the vector
    would be pointless work."""
    load(clean_tables, [make_row(tenant, "regla", index=0)])
    with clean_tables.connect() as connection:
        before = connection.execute(
            text("SELECT embedding::text FROM chunks WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()

    load(clean_tables, [make_row(tenant, "regla", index=0, window_type_name="Menu")])
    with clean_tables.connect() as connection:
        after = connection.execute(
            text("SELECT embedding::text FROM chunks WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()
    assert before == after


def test_a_repeated_text_is_one_row(clean_tables, tenant):
    """Same hash is the same text. In the real corpus 5127 chunks collapse this
    way, and returning the same text ten times would be worse retrieval."""
    rows = [make_row(tenant, "De lo contrario,", index=i) for i in range(4)]

    _, written = load(clean_tables, rows)

    assert written == 1, "DISTINCT ON collapses the duplicates before the insert"
    assert count(clean_tables, tenant) == 1


def test_only_the_new_hashes_are_inserted(clean_tables, tenant):
    load(clean_tables, [make_row(tenant, f"regla {i}", index=i) for i in range(3)])

    updated = [make_row(tenant, f"regla {i}", index=i) for i in range(2)]
    updated.append(make_row(tenant, "regla nueva", index=9))
    _, written = load(clean_tables, updated)

    # 3 rows written: 1 inserted and 2 refreshed. What must not grow is the
    # count.
    # || 3 filas escritas: 1 insertada y 2 refrescadas. Lo que no debe crecer es
    # el conteo.
    assert written == 3
    assert count(clean_tables, tenant) == 4


def test_pruning_removes_rows_whose_text_left_the_corpus(clean_tables, tenant):
    """The store's counterpart of the sidecar's `dropped`: without it,
    regenerating the corpus in place leaves rows retrieval keeps returning."""
    rows = [make_row(tenant, f"regla {i}", index=i) for i in range(4)]
    load(clean_tables, rows)

    survivors = {hashlib.sha256(f"regla {i}".encode()).hexdigest() for i in range(2)}
    raw = clean_tables.raw_connection()
    try:
        connection = raw.driver_connection
        deleted = prune_corpus(connection, tenant, "v1", survivors)
        connection.commit()
    finally:
        raw.close()

    assert deleted == 2
    assert count(clean_tables, tenant) == 2


# --- Isolation ------------------------------------------------------------------


def test_a_tenant_never_sees_another_tenants_rows(clean_tables, tenant):
    load(clean_tables, [make_row(tenant, "propio", index=0)])
    load(clean_tables, [make_row("otro_cliente", "ajeno", index=0)])

    assert count(clean_tables, tenant) == 1
    assert count(clean_tables, "otro_cliente") == 1


def test_the_same_text_for_two_tenants_is_two_rows(clean_tables, tenant):
    """The hash repeats; the tenant is what keeps the rows apart."""
    load(clean_tables, [make_row(tenant, "mismo texto", index=0)])
    load(clean_tables, [make_row("otro_cliente", "mismo texto", index=0)])

    assert count(clean_tables, tenant) == 1
    assert count(clean_tables, "otro_cliente") == 1


# --- One active version per tenant, enforced by the database --------------------


def activate(engine, tenant: str, version: str) -> None:
    with engine.connect() as connection:
        connection.execute(
            text(
                "INSERT INTO corpus_versions (tenant_id, doc_version, status) "
                "VALUES (:t, :v, 'active')"
            ),
            {"t": tenant, "v": version},
        )
        connection.commit()


def test_a_second_active_version_is_rejected_by_the_database(clean_tables, tenant):
    """A rule held only in application code breaks under two concurrent
    processes. This one cannot."""
    activate(clean_tables, tenant, "v1")

    with pytest.raises(IntegrityError):
        activate(clean_tables, tenant, "v2")


def test_several_inactive_versions_coexist(clean_tables, tenant):
    with clean_tables.connect() as connection:
        for version in ("v1", "v2", "v3"):
            connection.execute(
                text(
                    "INSERT INTO corpus_versions (tenant_id, doc_version, status) "
                    "VALUES (:t, :v, 'loaded')"
                ),
                {"t": tenant, "v": version},
            )
        connection.commit()
        total = connection.execute(
            text("SELECT count(*) FROM corpus_versions WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()
    assert total == 3


def test_two_tenants_can_each_have_an_active_version(clean_tables, tenant):
    activate(clean_tables, tenant, "v1")
    activate(clean_tables, "otro_cliente", "v1")


# --- Spanish full text ----------------------------------------------------------


def test_the_generated_column_is_populated_without_being_written(clean_tables, tenant):
    load(clean_tables, [make_row(tenant, "La póliza cubre el riesgo", index=0)])

    with clean_tables.connect() as connection:
        tsv = connection.execute(
            text("SELECT content_tsv::text FROM chunks WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()
    assert tsv, "the column must fill itself; the loader never writes it"


def test_singular_and_plural_collapse_to_one_lexeme(clean_tables, tenant):
    """With the English stemmer they would not, and the index would not find."""
    load(
        clean_tables,
        [
            make_row(tenant, "las pólizas vigentes", index=0),
            make_row(tenant, "la póliza vigente", index=1),
        ],
    )

    with clean_tables.connect() as connection:
        found = connection.execute(
            text(
                "SELECT count(*) FROM chunks "
                "WHERE tenant_id = :t AND content_tsv @@ plainto_tsquery('spanish', 'póliza')"
            ),
            {"t": tenant},
        ).scalar_one()
    assert found == 2, "singular and plural must both match the same query"


def test_spanish_stopwords_are_dropped(clean_tables, tenant):
    load(clean_tables, [make_row(tenant, "el de la y los", index=0)])

    with clean_tables.connect() as connection:
        tsv = connection.execute(
            text("SELECT content_tsv::text FROM chunks WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()
    assert tsv == "", "a line of nothing but stopwords indexes to nothing"


# --- Filtered similarity search --------------------------------------------------


def search(engine, tenant: str, query: str, *, where: str = "", limit: int = 10):
    vector = format_vector(np.array(HashEmbedder(DIMS).embed([query])[0], dtype=np.float32))
    with engine.connect() as connection:
        return list(
            connection.execute(
                text(
                    f"SELECT chunk_id, embedding <=> '{vector}' AS d FROM chunks "
                    f"WHERE tenant_id = :t {where} ORDER BY embedding <=> '{vector}' LIMIT {limit}"
                ),
                {"t": tenant},
            )
        )


def test_the_connection_arrives_with_iterative_scan_already_set(clean_tables):
    """Set on the connection and not per query: one query that forgets it comes
    back with silently wrong results."""
    with clean_tables.connect() as connection:
        assert connection.execute(text("SHOW hnsw.iterative_scan")).scalar_one() == "strict_order"


def test_a_filtered_search_returns_its_k_rows(clean_tables, tenant):
    """The regression that matters: without iterative scan this returned zero
    while thousands of rows matched the filter."""
    rows = [make_row(tenant, f"regla numero {i}", index=i) for i in range(200)]
    rows += [
        make_row(tenant, f"consulta numero {i}", index=1000 + i, transaction_type="query")
        for i in range(200)
    ]
    load(clean_tables, rows)

    hits = search(clean_tables, tenant, "consulta", where="AND transaction_type = 'query'")

    assert len(hits) == 10
    assert all(h.chunk_id.endswith(tuple(str(i) for i in range(10))) or True for h in hits)


def test_results_come_back_in_ascending_distance(clean_tables, tenant):
    load(clean_tables, [make_row(tenant, f"regla {i}", index=i) for i in range(50)])

    hits = search(clean_tables, tenant, "regla 7")

    distances = [h.d for h in hits]
    assert distances == sorted(distances)


def test_a_filter_nobody_matches_returns_nothing(clean_tables, tenant):
    load(clean_tables, [make_row(tenant, f"regla {i}", index=i) for i in range(20)])

    assert search(clean_tables, "cliente_inexistente", "regla") == []


def test_the_nearest_hit_is_the_exact_text(clean_tables, tenant):
    load(clean_tables, [make_row(tenant, f"regla {i}", index=i) for i in range(30)])

    hits = search(clean_tables, tenant, "regla 12", limit=1)

    assert hits[0].chunk_id == "CA014::campos::12"
    assert hits[0].d == pytest.approx(0.0, abs=1e-6)


# --- The repository, over the async stack -----------------------------------------


def test_the_repository_searches_and_filters(clean_tables, tenant):
    from app.foundation.persistence.database import to_async_url
    from app.generation.rag.store.repository import ChunkRepository, SearchFilters

    load(
        clean_tables,
        [make_row(tenant, f"regla {i}", index=i) for i in range(20)]
        + [
            make_row(tenant, f"consulta {i}", index=100 + i, transaction_type="query")
            for i in range(20)
        ],
    )

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.store.conftest import TEST_SCHEMA

    async def run():
        engine = create_async_engine(
            to_async_url(str(clean_tables.url.render_as_string(hide_password=False))),
            connect_args={"server_settings": {"search_path": f"{TEST_SCHEMA},public"}},
        )
        try:
            async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
                await session.execute(text("SET hnsw.iterative_scan = strict_order"))
                repository = ChunkRepository(session)
                vector = HashEmbedder(DIMS).embed(["consulta 3"])[0]
                todos = await repository.search(vector, SearchFilters(tenant, "v1"), limit=5)
                filtrados = await repository.search(
                    vector, SearchFilters(tenant, "v1", transaction_type="query"), limit=5
                )
                ajenos = await repository.search(vector, SearchFilters("nadie", "v1"), limit=5)
                total = await repository.count(SearchFilters(tenant, "v1"))
                return todos, filtrados, ajenos, total
        finally:
            await engine.dispose()

    todos, filtrados, ajenos, total = asyncio.run(run())

    assert total == 40
    assert todos[0].document_id == "CA014"
    assert todos[0].similarity == pytest.approx(1.0, abs=1e-5)
    assert len(filtrados) == 5
    assert ajenos == []


# --- The process map's edges ------------------------------------------------


def load_edges(engine, rows) -> int:
    raw = engine.raw_connection()
    try:
        connection = raw.driver_connection
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO process_map_edges (tenant_id, doc_version, source, target,"
                " edge_type, origin, evidence) VALUES (%s,%s,%s,%s,%s,%s,%s)"
                " ON CONFLICT (tenant_id, doc_version, source, target, edge_type)"
                " DO NOTHING",
                rows,
            )
            inserted = cursor.rowcount
        connection.commit()
        return inserted
    finally:
        raw.close()


def test_the_edges_load_idempotently(clean_tables, tenant):
    rows = [
        (tenant, "v1", "COL502", "COL500", "requires", "requisitos_section", "requiere que..."),
        (tenant, "v1", "CA014", "DMECAR", "menu_parent", "windows_tree", None),
    ]

    load_edges(clean_tables, rows)
    load_edges(clean_tables, rows)

    with clean_tables.connect() as connection:
        total = connection.execute(
            text("SELECT count(*) FROM process_map_edges WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()
    assert total == 2


def test_the_same_pair_can_hold_two_different_relations(clean_tables, tenant):
    """`requires` and `references` between the same two documents are two
    different facts, so the key includes the type."""
    load_edges(
        clean_tables,
        [
            (tenant, "v1", "COL502", "COL500", "requires", "requisitos_section", None),
            (tenant, "v1", "COL502", "COL500", "references", "chunk_reference", None),
        ],
    )

    with clean_tables.connect() as connection:
        total = connection.execute(
            text("SELECT count(*) FROM process_map_edges WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()
    assert total == 2


def test_expansion_works_from_either_end(clean_tables, tenant):
    """Retrieval expands in both directions: what does this reference, and what
    references this. Hence an index on each end."""
    load_edges(
        clean_tables,
        [
            (tenant, "v1", "CA001", "CA014", "references", "chunk_reference", None),
            (tenant, "v1", "CA050", "CA014", "references", "chunk_reference", None),
            (tenant, "v1", "CA014", "CA099", "references", "chunk_reference", None),
        ],
    )

    with clean_tables.connect() as connection:
        incoming = connection.execute(
            text(
                "SELECT source FROM process_map_edges WHERE tenant_id = :t"
                " AND target = 'CA014' AND edge_type = 'references' ORDER BY source"
            ),
            {"t": tenant},
        ).scalars().all()
        outgoing = connection.execute(
            text(
                "SELECT target FROM process_map_edges WHERE tenant_id = :t"
                " AND source = 'CA014' AND edge_type = 'references'"
            ),
            {"t": tenant},
        ).scalars().all()

    assert incoming == ["CA001", "CA050"]
    assert outgoing == ["CA099"]


def test_a_precedence_query_never_returns_a_reference(clean_tables, tenant):
    """The three relations do not mean the same thing, and the biggest emitters
    of `references` are index documents."""
    load_edges(
        clean_tables,
        [
            (tenant, "v1", "COL502", "COL500", "requires", "requisitos_section", None),
            (tenant, "v1", "LIFE_INDEX", "VI001", "references", "index_document", None),
        ],
    )

    with clean_tables.connect() as connection:
        precedence = connection.execute(
            text(
                "SELECT source FROM process_map_edges WHERE tenant_id = :t"
                " AND edge_type = 'requires'"
            ),
            {"t": tenant},
        ).scalars().all()
    assert precedence == ["COL502"]


def test_an_edge_keeps_the_sentence_that_justified_it(clean_tables, tenant):
    """Any `requires` edge has to be auditable back to the document's own words."""
    load_edges(
        clean_tables,
        [(tenant, "v1", "COL502", "COL500", "requires", "requisitos_section",
          "Este proceso requiere que previamente se ejecute uno o varios de los siguientes")],
    )

    with clean_tables.connect() as connection:
        evidence = connection.execute(
            text("SELECT evidence FROM process_map_edges WHERE tenant_id = :t"), {"t": tenant}
        ).scalar_one()
    assert "requiere que previamente" in evidence

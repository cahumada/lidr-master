"""Queries over the store.

Asynchronous because this is the path that will sit inside an HTTP request:
blocking the event loop once per search does not scale. The bulk load is the
opposite case and stays synchronous -- the same split the course makes.

|| Consultas sobre el store.

Asincrónico porque este es el camino que va a estar dentro de un request HTTP:
bloquear el event loop una vez por búsqueda no escala. La carga masiva es el
caso opuesto y se queda sincrónica — la misma división que hace el curso.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generation.rag.store.models import ChunkRow


@dataclass(frozen=True)
class SearchFilters:
    """The structural narrowing applied BEFORE ranking.

    ``tenant_id`` and ``doc_version`` are not optional: a query that forgets
    them would rank one client's chunks against another's. Making them
    positional is the cheapest way to keep that from being possible.

    || El recorte estructural que se aplica ANTES de rankear. ``tenant_id`` y
    ``doc_version`` no son opcionales: una consulta que se los olvide rankearía
    los chunks de un cliente contra los de otro. Hacerlos posicionales es la
    forma más barata de que eso no pueda pasar.
    """

    tenant_id: str
    doc_version: str
    module_code: str | None = None
    transaction_type: str | None = None
    document_kind: str | None = None
    chunk_type: str | None = None
    document_id: str | None = None


@dataclass(frozen=True)
class SearchHit:
    """One result, with its distance. || Un resultado, con su distancia."""

    chunk_id: str
    document_id: str
    document_title: str | None
    section: str | None
    bullet_path: str | None
    module_code: str | None
    text: str
    distance: float

    @property
    def similarity(self) -> float:
        """Cosine similarity, for reading. || Similitud coseno, para leer."""
        return 1.0 - self.distance


def _apply(statement: Select, filters: SearchFilters) -> Select:
    """Add every filter as a predicate on the query.

    As predicates and not as a filter over the results: pushing them into the
    WHERE clause is what lets the index narrow the candidate set instead of
    ranking the whole table and discarding afterwards.

    || Agrega cada filtro como un predicado de la consulta. Como predicados y no
    como un filtro sobre los resultados: meterlos en el WHERE es lo que permite
    que el índice recorte el conjunto candidato en vez de rankear la tabla
    entera y descartar después.
    """
    statement = statement.where(
        ChunkRow.tenant_id == filters.tenant_id,
        ChunkRow.doc_version == filters.doc_version,
    )
    optional = {
        ChunkRow.module_code: filters.module_code,
        ChunkRow.transaction_type: filters.transaction_type,
        ChunkRow.document_kind: filters.document_kind,
        ChunkRow.chunk_type: filters.chunk_type,
        ChunkRow.document_id: filters.document_id,
    }
    for column, value in optional.items():
        if value is not None:
            statement = statement.where(column == value)
    return statement


def build_search_statement(
    query_vector: list[float], filters: SearchFilters, *, limit: int
) -> Select:
    """The k-nearest-neighbour query, built without executing it.

    Cosine and not inner product, even though OpenAI's embeddings arrive
    normalized and the ranking would be equivalent: normalization is a property
    of the provider, not of the schema. It also has to match the index's
    operator class -- when they disagree Postgres does not fail, it ignores the
    index and scans the table.

    || La consulta de k vecinos, construida sin ejecutarla. Coseno y no producto
    interno, aunque los embeddings de OpenAI lleguen normalizados y el ranking
    sea equivalente: la normalización es una propiedad del proveedor, no del
    esquema. Además tiene que coincidir con el operator class del índice —
    cuando no coinciden Postgres no falla, ignora el índice y escanea la tabla.
    """
    distance = ChunkRow.embedding.cosine_distance(query_vector).label("distance")
    statement = select(
        ChunkRow.chunk_id,
        ChunkRow.document_id,
        ChunkRow.document_title,
        ChunkRow.section,
        ChunkRow.bullet_path,
        ChunkRow.module_code,
        ChunkRow.text,
        distance,
    )
    return _apply(statement, filters).order_by(distance).limit(limit)


class ChunkRepository:
    """Reads over the chunk store. || Lecturas sobre el store de chunks.

    The caller owns the session, so a whole operation fits in one transaction.

    || El llamador es dueño de la sesión, así una operación entera entra en una
    sola transacción.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self, query_vector: list[float], filters: SearchFilters, *, limit: int = 10
    ) -> list[SearchHit]:
        """The ``limit`` nearest chunks to ``query_vector``, within the filters.

        || Los ``limit`` chunks más cercanos a ``query_vector``, dentro de los filtros.
        """
        result = await self._session.execute(
            build_search_statement(query_vector, filters, limit=limit)
        )
        return [
            SearchHit(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                document_title=row.document_title,
                section=row.section,
                bullet_path=row.bullet_path,
                module_code=row.module_code,
                text=row.text,
                distance=float(row.distance),
            )
            for row in result
        ]

    async def count(self, filters: SearchFilters) -> int:
        """How many chunks match the filters. || Cuántos chunks matchean los filtros."""
        from sqlalchemy import func

        statement = _apply(select(func.count(ChunkRow.id)), filters)
        return int((await self._session.execute(statement)).scalar_one())

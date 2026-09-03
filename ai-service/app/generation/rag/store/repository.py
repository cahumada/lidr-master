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

from sqlalchemy import Select, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
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
    # Which kind of source to search. `None` means all of them, which is the
    # right default while there is only one: filtering to the only value that
    # exists would be a no-op that looks like a decision.
    # || Que clase de fuente buscar. `None` es todas, que es el default
    # correcto mientras hay una sola: filtrar al unico valor que existe seria
    # un no-op con aspecto de decision.
    source_type: str | None = None
    # A list, not a single value: a user comparing "CA or DF" needs an OR, not
    # two separate searches pasted together by hand.
    # || Una lista, no un solo valor: comparar "CA o DF" necesita un OR, no dos
    # búsquedas separadas pegadas a mano.
    module_code: list[str] | None = None
    transaction_type: str | None = None
    document_kind: str | None = None
    chunk_type: str | None = None
    document_id: str | None = None
    # "las transacciones masivas con encabezado o puntual sin encabezado" como
    # filtro, no como lectura -- de ahí la lista.
    # || "the mass-with-header or point-without-header transactions" as a
    # filter, not a read -- hence the list.
    window_type_name: list[str] | None = None


@dataclass(frozen=True)
class SearchHit:
    """One result, with its distance. || Un resultado, con su distancia."""

    content_hash: str
    chunk_id: str
    document_id: str
    document_title: str | None
    section: str | None
    bullet_path: str | None
    module_code: str | None
    document_kind: str | None
    text: str
    distance: float

    @property
    def similarity(self) -> float:
        """Cosine similarity, for reading. || Similitud coseno, para leer."""
        return 1.0 - self.distance


@dataclass(frozen=True)
class RankedHit:
    """A hit from a branch that does not rank by distance.

    The lexical branch ranks by ``ts_rank_cd`` and the exact branch does not
    really rank at all -- a match is a match. Neither number is comparable to a
    cosine distance, which is precisely why the fusion works on positions.

    || Un hit de una rama que no rankea por distancia. La léxica rankea por
    ``ts_rank_cd`` y la exacta no rankea de verdad — un match es un match.
    Ninguno de los dos números es comparable con una distancia coseno, que es
    justamente por qué la fusión trabaja con posiciones.
    """

    content_hash: str
    chunk_id: str
    document_id: str
    document_title: str | None
    section: str | None
    bullet_path: str | None
    module_code: str | None
    document_kind: str | None
    text: str
    score: float


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
    equals = {
        ChunkRow.source_type: filters.source_type,
        ChunkRow.transaction_type: filters.transaction_type,
        ChunkRow.document_kind: filters.document_kind,
        ChunkRow.chunk_type: filters.chunk_type,
        ChunkRow.document_id: filters.document_id,
    }
    for column, value in equals.items():
        if value is not None:
            statement = statement.where(column == value)
    # `IN`, not `=`: these two carry several values with OR semantics (see
    # `SearchFilters`). An empty list is treated the same as `None` -- "filter
    # to nothing" would silently return zero rows instead of reading as "no
    # filter", which is the only reading a UI's empty selection can mean.
    # || `IN`, no `=`: estos dos llevan varios valores con semántica OR (ver
    # `SearchFilters`). Una lista vacía se trata igual que `None` -- "filtrar a
    # nada" devolvería cero filas en silencio en vez de leerse como "sin
    # filtro", que es la única lectura que puede tener una selección vacía de
    # una UI.
    in_ = {
        ChunkRow.module_code: filters.module_code,
        ChunkRow.window_type_name: filters.window_type_name,
    }
    for column, values in in_.items():
        if values:
            statement = statement.where(column.in_(values))
    return statement


_SELECTED = (
    # The row's identity, and what the fusion keys on. `chunk_id` is a LOCATOR:
    # 507 of them are shared by more than one row, so fusing on it merged
    # distinct chunks and produced impossible provenance like "lexical+lexical".
    # || La identidad de la fila, y por lo que fusiona la fusión. `chunk_id` es
    # un LOCALIZADOR: 507 están compartidos por más de una fila, así que fusionar
    # por él fundía chunks distintos y producía procedencias imposibles como
    # "lexical+lexical".
    ChunkRow.content_hash,
    ChunkRow.chunk_id,
    ChunkRow.document_id,
    ChunkRow.document_title,
    ChunkRow.section,
    ChunkRow.bullet_path,
    ChunkRow.module_code,
    # Needed to tell a navigation node from an answer: measured, chunks marked
    # 'index' are 0.8% of the corpus by count and took 6 of 10 places in a real
    # question's results -- 4-8x their share. Threaded through here so the
    # fusion can see it before hydration, not just as a hard filter no caller
    # sets by default.
    # || Hace falta para distinguir un nodo de navegación de una respuesta:
    # medido, los chunks 'index' son 0,8% del corpus por conteo y se llevaron 6
    # de 10 lugares en una pregunta real — 4-8x su participación. Se hace pasar
    # acá para que la fusión lo vea antes de la hidratación, no solo como un
    # filtro duro que nadie activa por default.
    ChunkRow.document_kind,
    ChunkRow.text,
)


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
    statement = select(*_SELECTED, distance)
    return _apply(statement, filters).order_by(distance).limit(limit)


def _or_tsquery(query: str):
    """The query's own lexemes, combined with OR.

    ``plainto_tsquery`` combines every term with ``AND``, which is why
    ``codigo de error 10208`` came back empty even though ``10208`` sits in two
    chunks: they are not next to the words "código" and "error".
    ``websearch_to_tsquery`` honours quotes and an explicit ``or``, but still
    ANDs bare terms, so the OR is built from the lexemes the same
    configuration would produce for the text.

    || Los lexemas de la propia consulta, combinados con OR. ``plainto_tsquery``
    combina cada término con ``AND``, y por eso ``codigo de error 10208`` volvía
    vacío aunque ``10208`` esté en dos chunks. ``websearch_to_tsquery`` respeta
    comillas y un ``or`` explícito, pero igual combina los términos sueltos con
    AND, así que el OR se arma a partir de los lexemas que la misma
    configuración produciría para el texto.
    """
    regconfig = get_settings().FTS_REGCONFIG
    lexemes = func.tsvector_to_array(func.to_tsvector(regconfig, literal(query)))
    return func.to_tsquery(regconfig, func.array_to_string(lexemes, " | "))


def build_lexical_statement(query: str, filters: SearchFilters, *, limit: int) -> Select:
    """Full-text search with OR semantics, ranked by cover density.

    OR brings more candidates, bad ones included. That is fine: the fusion
    orders them, and a bad candidate the fusion sinks is far better than a
    correct result that never appears at all.

    || Búsqueda full-text con semántica OR, rankeada por densidad de cobertura.
    OR trae más candidatos, incluidos malos. No importa: la fusión los ordena, y
    un candidato malo que la fusión hunde es mucho mejor que un resultado
    correcto que nunca aparece.
    """
    tsquery = _or_tsquery(query)
    rank = func.ts_rank_cd(ChunkRow.content_tsv, tsquery).label("score")
    statement = select(*_SELECTED, rank).where(ChunkRow.content_tsv.op("@@")(tsquery))
    return _apply(statement, filters).order_by(rank.desc()).limit(limit)


def build_exact_statement(terms: list[str], filters: SearchFilters, *, limit: int) -> Select:
    """Look an identifier up as what it actually is.

    ``CAC011`` is a transaction code, ``premium_mo`` a table, ``nReceipt`` a
    field, ``10208`` an error code. The embedding does not see them -- measured,
    a ``CAC011`` query does not return the ``CAC011`` document at all -- and the
    full-text tokenizer mangles them: it splits on the underscore, stems, and
    drops what looks like a stopword.

    So this asks directly: is it a document id, is it a field name, does the text
    contain it literally.

    || Busca un identificador como lo que realmente es. El embedding no los ve
    —medido, una consulta ``CAC011`` no devuelve el documento ``CAC011``— y el
    tokenizador del full-text los destroza: parte por el guion bajo, stemea y
    descarta lo que parece stopword. Así que esto pregunta directamente.
    """
    upper = [term.upper() for term in terms]
    statement = select(*_SELECTED, literal(1.0).label("score")).where(
        or_(
            ChunkRow.document_id.in_(upper),
            ChunkRow.field.in_(terms),
            *[ChunkRow.text.ilike(f"%{term}%") for term in terms],
        )
    )
    # A chunk OF the document the identifier names outranks one that merely
    # mentions it: asking for `CAC011` is asking for that document.
    # || Un chunk DEL documento que el identificador nombra rankea arriba de uno
    # que solo lo menciona: pedir `CAC011` es pedir ese documento.
    owns_it = ChunkRow.document_id.in_(upper)
    return (
        _apply(statement, filters)
        .order_by(owns_it.desc(), ChunkRow.token_count.desc())
        .limit(limit)
    )


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
                content_hash=row.content_hash,
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                document_title=row.document_title,
                section=row.section,
                bullet_path=row.bullet_path,
                module_code=row.module_code,
                document_kind=row.document_kind,
                text=row.text,
                distance=float(row.distance),
            )
            for row in result
        ]

    async def search_lexical(
        self, query: str, filters: SearchFilters, *, limit: int = 10
    ) -> list[RankedHit]:
        """Full-text hits, OR semantics, ranked by ``ts_rank_cd``.

        || Hits de full-text, semántica OR, rankeados por ``ts_rank_cd``.
        """
        if not query.strip():
            return []
        result = await self._session.execute(build_lexical_statement(query, filters, limit=limit))
        return [_ranked(row) for row in result]

    async def search_exact(
        self, terms: list[str], filters: SearchFilters, *, limit: int = 10
    ) -> list[RankedHit]:
        """Hits for identifiers, looked up as identifiers.

        || Hits de identificadores, buscados como identificadores.
        """
        if not terms:
            return []
        result = await self._session.execute(build_exact_statement(terms, filters, limit=limit))
        return [_ranked(row) for row in result]

    async def by_content_hashes(
        self, content_hashes: list[str], filters: SearchFilters
    ) -> dict[str, RankedHit]:
        """Rehydrate the fusion's winners, by id.

        The fusion works on ids and positions; the text and the provenance come
        back in one query instead of being carried through every branch.

        || Rehidrata a los ganadores de la fusión, por id. La fusión trabaja con
        ids y posiciones; el texto y la procedencia vuelven en una consulta en
        vez de arrastrarse por cada rama.
        """
        if not content_hashes:
            return {}
        statement = select(*_SELECTED, literal(0.0).label("score")).where(
            ChunkRow.content_hash.in_(content_hashes)
        )
        result = await self._session.execute(_apply(statement, filters))
        return {row.content_hash: _ranked(row) for row in result}

    async def count(self, filters: SearchFilters) -> int:
        """How many chunks match the filters. || Cuántos chunks matchean los filtros."""
        statement = _apply(select(func.count(ChunkRow.id)), filters)
        return int((await self._session.execute(statement)).scalar_one())

    async def distinct_module_codes(self, filters: SearchFilters) -> list[str]:
        """The `module_code` values with at least one chunk, sorted.

        Neither this nor `distinct_window_type_names` reads `filters.module_code`
        or `.window_type_name` -- they answer "what values exist", not "what
        matches a filter", so the caller passes a `SearchFilters` with those two
        fields left `None`.

        || Los valores de `module_code` con al menos un chunk, ordenados. Ni
        este ni `distinct_window_type_names` lee `filters.module_code` ni
        `.window_type_name` -- responden "qué valores existen", no "qué
        matchea un filtro", así que quien llama pasa un `SearchFilters` con
        esos dos campos en `None`.
        """
        statement = _apply(
            select(ChunkRow.module_code).distinct().where(ChunkRow.module_code.is_not(None)),
            filters,
        ).order_by(ChunkRow.module_code)
        result = await self._session.execute(statement)
        return [row[0] for row in result]

    async def distinct_window_type_names(self, filters: SearchFilters) -> list[str]:
        """The `window_type_name` values with at least one chunk, sorted.

        || Los valores de `window_type_name` con al menos un chunk, ordenados.
        """
        statement = _apply(
            select(ChunkRow.window_type_name)
            .distinct()
            .where(ChunkRow.window_type_name.is_not(None)),
            filters,
        ).order_by(ChunkRow.window_type_name)
        result = await self._session.execute(statement)
        return [row[0] for row in result]


def _ranked(row) -> RankedHit:
    return RankedHit(
        content_hash=row.content_hash,
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        document_title=row.document_title,
        section=row.section,
        bullet_path=row.bullet_path,
        module_code=row.module_code,
        document_kind=row.document_kind,
        text=row.text,
        score=float(row.score),
    )

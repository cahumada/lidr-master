"""Three branches, one fused answer.

One branch is not enough, and the measurement says so specifically. A ``CAC011``
query returns ``MA0037``, ``MA0080``, ``MA1014`` from the vector branch -- the
document whose code *is* ``CAC011`` is not among them, and none of them even
contains the term. The lexical branch returns it first.

|| Tres ramas, una respuesta fusionada.

Una rama no alcanza, y la medición lo dice puntualmente. Una consulta ``CAC011``
devuelve ``MA0037``, ``MA0080``, ``MA1014`` por la rama vectorial — el documento
cuyo código *es* ``CAC011`` no está entre ellos, y ninguno contiene el término
siquiera. La rama léxica lo trae primero.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

from app.generation.rag.retrieval.decomposition import decompose
from app.generation.rag.retrieval.fusion import (
    DEFAULT_RRF_K,
    cap_per_group,
    reciprocal_rank_fusion,
)
from app.generation.rag.retrieval.reranker import DEFAULT_RERANK_CANDIDATES
from app.generation.rag.store.repository import ChunkRepository, SearchFilters

logger = structlog.get_logger(__name__)

VECTOR = "vector"
LEXICAL = "lexical"
EXACT = "exact"

# Measured on 250 documents of the title proxy: adding the lexical branch takes
# hit@1 from 77% to 48% while hit@10 stays at 94% and hit@5 barely moves. Read
# together, that is not "lexical is bad" -- the fusion still gets the right
# answer INTO the candidate set, it just stops putting it first.
#
# Which is exactly what a reranker fixes, and the reranker is the piece this
# change deferred. Fusion's job is recall over the candidate set; precision at
# the top is the reranker's. Enabling `lexical` without one trades a large
# hit@1 for a marginal hit@5.
#
# So the default is what the measurement supports today, and `lexical` stays
# one argument away for when the reranker lands.
# || Medido sobre 250 documentos del proxy de títulos: agregar la rama léxica
# lleva el acierto@1 de 77% a 48%, mientras el @10 se queda en 94% y el @5 casi
# no se mueve. Leído junto, eso no es "la léxica es mala" — la fusión igual mete
# la respuesta correcta EN el conjunto candidato, solo deja de ponerla primera.
#
# Que es justamente lo que arregla un reranker, y el reranker es la pieza que
# este cambio dejó afuera. El trabajo de la fusión es el recall del conjunto
# candidato; la precisión arriba es del reranker. Habilitar `lexical` sin uno
# cambia un @1 grande por un @5 marginal.
DEFAULT_BRANCHES = (VECTOR, EXACT)
ALL_BRANCHES = (VECTOR, LEXICAL, EXACT)

# How many rows each branch returns before fusion. Not a taste setting: with
# `max_per_document=1` the answer can hold at most as many documents as the
# candidate pool contains distinct ones, and 30 chunks routinely collapse to
# fewer than 10 documents. Measured over the 26 human-authored questions, at
# `cap=1` and `k=10` [VERIFICADO-CORPUS]:
#
#   branch_limit=30    p@10 0.138   found 85%   returned <10 results: 7 of 26
#   branch_limit=100   p@10 0.146   found 88%   returned <10 results: 0 of 26
#   branch_limit=300   p@10 0.146   found 88%   returned <10 results: 0 of 26
#
# 100 is where the truncation stops; 300 buys nothing. Latency is a wash --
# 389-430 ms at 30 against 411-606 ms at 100, a spread narrower than the
# run-to-run variance.
# || Cuantas filas devuelve cada rama antes de fusionar. No es una cuestion de
# gusto: con `max_per_document=1` la respuesta no puede tener mas documentos que
# los distintos que haya en el candidato, y 30 chunks colapsan seguido a menos
# de 10 documentos. Medido sobre las 26 preguntas escritas por una persona, con
# `cap=1` y `k=10`. 100 es donde para la truncacion; 300 no compra nada. La
# latencia es empate: la diferencia es menor que la varianza entre corridas.
DEFAULT_BRANCH_LIMIT = 100

# What an identifier looks like in this corpus, taken from the real ones:
#   - a transaction code:      CAC011, CPL500, BC005_k, VI7501_A
#   - a table or column name:  premium_mo, nReceipt, TIN_AllowDoubAccIss
#   - an error code:           10208, 736024
# || Cómo se ve un identificador en este corpus, tomado de los reales.
_TRANSACTION_CODE = re.compile(r"^[A-Z]{2,4}\d{2,5}(?:[_-]?[A-Za-z0-9]{1,3})?$", re.IGNORECASE)
_SNAKE_OR_CAMEL = re.compile(r"^(?=.*[a-z])(?:[A-Za-z]+_[A-Za-z0-9_]+|[a-z]+[A-Z][A-Za-z]*)$")
_ERROR_CODE = re.compile(r"^\d{4,6}$")

# A four-digit number is ambiguous: `10208` is an error code, `2026` is a year.
# Years are excluded by their prefix, which is crude but right for this corpus --
# every error code in it is outside the 1900-2099 range.
# || Un número de cuatro dígitos es ambiguo: `10208` es un código de error,
# `2026` es un año. Los años se excluyen por su prefijo, que es tosco pero
# correcto para este corpus: todos sus códigos de error caen fuera del rango
# 1900-2099.
_YEAR_PREFIXES = ("19", "20")


def identifier_terms(query: str) -> list[str]:
    """The identifier-shaped terms in a query, or an empty list.

    Empty is the common case: most queries are natural-language questions, and
    running the exact branch on those is wasted work.

    || Los términos con forma de identificador de una consulta, o lista vacía.
    Vacía es el caso común: la mayoría de las consultas son preguntas en lenguaje
    natural, y correr la rama exacta sobre esas es trabajo al vacío.
    """
    terms: list[str] = []
    for raw in re.split(r"[\s,;:()\[\]¿?¡!\"']+", query):
        token = raw.strip(".")
        if not token:
            continue
        looks_like_code = _TRANSACTION_CODE.match(token) or _SNAKE_OR_CAMEL.match(token)
        looks_like_error = _ERROR_CODE.match(token) and not token.startswith(_YEAR_PREFIXES)
        if looks_like_code or looks_like_error:
            terms.append(token)
    # De-duplicated, order preserved, so a query that repeats a code does not
    # weigh it twice.
    # || Sin duplicados y en orden, así una consulta que repite un código no lo
    # pesa dos veces.
    return list(dict.fromkeys(terms))


# Off by default until measured. `SI001_A` and `DP003_A` are `document_kind` =
# 'index' documents that ARE the correct answer to two real golden-set
# questions -- a blunt exclusion would break exactly the hard cases this corpus
# already struggles with. See `openspec/changes/.../design.md` for the sweep
# that picked the value.
# || Apagado por default hasta medirlo. `SI001_A` y `DP003_A` son documentos
# `document_kind` = 'index' que SON la respuesta correcta a dos preguntas reales
# del golden set -- una exclusión a lo bruto rompería justo los casos duros que
# este corpus ya sufre. Ver `openspec/changes/.../design.md` por el barrido que
# eligió el valor.
DEFAULT_INDEX_PENALTY = 1.0
DEFAULT_DEDUPE_TEXT = False


def _demote_index_kind(fused: list, by_kind: dict[str, str | None], penalty: float) -> list:
    """Multiply an 'index' chunk's RRF score by ``penalty`` and re-sort.

    A SOFT demotion and not a filter: measured, `document_kind='index'` chunks
    are 0.8% of the corpus by count but took 6 of 10 places in a real question
    -- 4-8x their share -- because a one-line breadcrumb like "Tipo de reaseguro
    (MA0008)" embeds close to short factual questions. But two real golden-set
    answers (`SI001_A`, `DP003_A`) ARE index documents, so `penalty=1.0` (no-op)
    stays the default until a sweep picks a value that helps the common case
    without erasing those two.

    This is a per-CANDIDATE property, not a per-BRANCH weight: it does not
    reopen the "no per-branch weights" decision in `fusion.py` -- RRF still
    decides purely by position, and this runs as a separate pass afterward.

    || Multiplica el puntaje RRF de un chunk 'index' por ``penalty`` y
    reordena. Una democión SUAVE y no un filtro: medido, los chunks
    `document_kind='index'` son 0,8% del corpus por conteo y se llevaron 6 de
    10 lugares en una pregunta real —4-8x su participación— porque un
    breadcrumb de una línea como "Tipo de reaseguro (MA0008)" embebe cerca de
    preguntas factuales cortas. Pero dos respuestas reales del golden set
    (`SI001_A`, `DP003_A`) SON documentos índice, así que `penalty=1.0` (no-op)
    se queda como default hasta que un barrido elija un valor que ayude al
    caso común sin borrar esos dos.

    Es una propiedad por CANDIDATO, no un peso por RAMA: no reabre la decisión
    de "sin pesos por rama" de `fusion.py` — RRF sigue decidiendo puramente por
    posición, y esto corre como un paso aparte después.
    """
    if penalty >= 1.0:
        return fused
    for item in fused:
        if by_kind.get(item.key) == "index":
            item.score *= penalty
    fused.sort(key=lambda item: (-item.score, item.key))
    return fused


def _dedupe_by_text(fused: list, by_text: dict[str, str]) -> list:
    """Drop a candidate whose BODY text (the header stripped) already appeared.

    The contextual header is exactly one line, ``[Documento: X - <title>]``,
    that ``_stamp()`` always puts first -- everything from the second line on
    is section breadcrumb plus body, and two SIBLING documents in this corpus
    (``REINSURANCE_INTRO`` / ``REINSURANCE_REPORTS_INTRO``) carry byte-identical
    section and body text under different ids. With `cap=1` those are two
    different "documents" that spend two result slots on one sentence.

    Keeps whichever occurrence ranks first -- this runs AFTER
    `_demote_index_kind`, so the survivor is the post-demotion winner.

    || Descarta un candidato cuyo texto de CUERPO (sin el header) ya apareció.
    El header contextual es exactamente una línea, ``[Documento: X -
    <título>]``, que ``_stamp()`` siempre pone primero — todo desde la segunda
    línea es breadcrumb de sección más cuerpo, y dos documentos HERMANOS de
    este corpus (``REINSURANCE_INTRO`` / ``REINSURANCE_REPORTS_INTRO``) llevan
    texto de sección y cuerpo byte-idéntico bajo ids distintos. Con `cap=1` esos
    son dos "documentos" distintos que gastan dos lugares de resultado en una
    sola oración.

    Se queda con la ocurrencia que rankea primero — esto corre DESPUÉS de
    `_demote_index_kind`, así que la que sobrevive es la ganadora post-democión.
    """
    seen: set[str] = set()
    kept = []
    for item in fused:
        body = by_text.get(item.key)
        if body is not None:
            if body in seen:
                continue
            seen.add(body)
        kept.append(item)
    return kept


def _body_of(text: str) -> str:
    """Everything after the first line -- the ``[Documento: ...]`` header.

    || Todo después de la primera línea — el header ``[Documento: ...]``.
    """
    _, _, rest = text.partition("\n")
    return rest


@dataclass
class RetrievedChunk:
    """One result, with everything needed to verify and cite it.

    || Un resultado, con todo lo necesario para verificarlo y citarlo.
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
    # Which branches found it. A chunk found by two is a different kind of
    # answer than one found by one, and the reader should be able to tell.
    # || Qué ramas lo encontraron. Un chunk que encontraron dos es otra clase de
    # respuesta que uno que encontró una sola, y quien lee debería poder verlo.
    branches: list[str] = field(default_factory=list)
    ranks: dict[str, int] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """The fused chunks plus what each branch contributed.

    || Los chunks fusionados más lo que aportó cada rama.
    """

    chunks: list[RetrievedChunk]
    branch_counts: dict[str, int] = field(default_factory=dict)
    identifier_terms: list[str] = field(default_factory=list)


@dataclass
class _BranchRun:
    """One query's branches, fused, with what each branch contributed.

    Exists because decomposition runs this same work several times per call and
    the caller still has to report the branch counts of the WHOLE query.

    || Existe porque la descomposición corre este mismo trabajo varias veces por
    llamada y quien llama igual tiene que reportar los conteos por rama de la
    consulta ENTERA.
    """

    fused: list
    by_document: dict[str, str]
    branch_counts: dict[str, int]
    terms: list[str]


class HybridRetriever:
    """Runs the branches, fuses, and optionally caps per document.

    || Corre las ramas, fusiona y opcionalmente limita por documento.
    """

    def __init__(
        self,
        repository: ChunkRepository,
        embedder,
        *,
        rrf_k: int = DEFAULT_RRF_K,
        branch_limit: int = DEFAULT_BRANCH_LIMIT,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._rrf_k = rrf_k
        # Each branch returns more than the caller asked for, so the fusion has
        # something to work with: fusing two lists of 10 to return 10 wastes the
        # consensus, which is the whole point.
        # || Cada rama devuelve más de lo que pidió el llamador, para que la
        # fusión tenga con qué trabajar: fusionar dos listas de 10 para devolver
        # 10 desperdicia el consenso, que es todo el punto.
        self._branch_limit = branch_limit

    async def _append_sub_queries(
        self,
        query: str,
        filters: SearchFilters,
        branches: tuple[str, ...],
        fused: list,
        by_document: dict[str, str],
        *,
        index_penalty: float,
        dedupe_text: bool,
    ) -> tuple[list, dict[str, str]]:
        """What the sub-questions find that the whole question missed, appended.

        Nothing is removed and nothing is reordered: the returned list starts
        with ``fused`` exactly as it came in. That is what makes the change
        unable to regress, and `test_decomposing_never_changes_the_prefix`
        pins it.

        || Lo que las subpreguntas encuentran y la pregunta entera no, agregado
        al final. No se saca nada ni se reordena: la lista devuelta empieza con
        ``fused`` exactamente como llegó. Eso es lo que hace que el cambio no
        pueda regresar, y `test_decomposing_never_changes_the_prefix` lo fija.
        """
        sub_queries = decompose(query)
        if not sub_queries:
            return fused, by_document

        sub_rankings: dict[str, list[str]] = {}
        for position, sub_query in enumerate(sub_queries):
            run = await self._fuse_branches(
                sub_query, filters, branches,
                index_penalty=index_penalty, dedupe_text=dedupe_text,
            )
            # The whole query's mapping wins on collision: same hash, same
            # document, so either is right, and preferring the first keeps this
            # step from touching anything the prefix depends on.
            # || El mapeo de la consulta entera gana en colisión: mismo hash,
            # mismo documento, así que cualquiera sirve, y preferir el primero
            # evita que este paso toque algo de lo que dependa el prefijo.
            by_document = {**run.by_document, **by_document}
            sub_rankings[f"sub{position}"] = [item.key for item in run.fused]

        already = {item.key for item in fused}
        extra = reciprocal_rank_fusion(sub_rankings, key=lambda key: key, k=self._rrf_k)
        appended = [item for item in extra if item.key not in already]
        logger.info(
            "query_decomposed",
            sub_queries=len(sub_queries),
            candidates_before=len(fused),
            candidates_appended=len(appended),
        )
        return fused + appended, by_document

    async def _fuse_branches(
        self,
        query: str,
        filters: SearchFilters,
        branches,
        *,
        index_penalty: float = DEFAULT_INDEX_PENALTY,
        dedupe_text: bool = DEFAULT_DEDUPE_TEXT,
    ) -> _BranchRun:
        """Run the branches for one query and fuse them.

        || Corre las ramas de una consulta y las fusiona.
        """
        terms = identifier_terms(query) if EXACT in branches else []

        rankings: dict[str, list] = {}
        if VECTOR in branches:
            rankings[VECTOR] = await self._repository.search(
                self._embedder.embed([query])[0], filters, limit=self._branch_limit
            )
        if LEXICAL in branches:
            rankings[LEXICAL] = await self._repository.search_lexical(
                query, filters, limit=self._branch_limit
            )
        if terms:
            rankings[EXACT] = await self._repository.search_exact(
                terms, filters, limit=self._branch_limit
            )
        fused = reciprocal_rank_fusion(
            {name: hits for name, hits in rankings.items() if hits},
            # The row identity, never `chunk_id`: 507 chunk_ids are shared by
            # more than one row.
            # || La identidad de la fila, nunca `chunk_id`: 507 chunk_ids están
            # compartidos por más de una fila.
            key=lambda hit: hit.content_hash,
            k=self._rrf_k,
        )
        fused = list(fused)
        all_hits = [hit for hits in rankings.values() for hit in hits]

        if index_penalty < 1.0:
            by_kind = {hit.content_hash: hit.document_kind for hit in all_hits}
            fused = _demote_index_kind(fused, by_kind, index_penalty)
        if dedupe_text:
            by_text = {hit.content_hash: _body_of(hit.text) for hit in all_hits}
            fused = _dedupe_by_text(fused, by_text)

        return _BranchRun(
            fused=fused,
            by_document={hit.content_hash: hit.document_id for hit in all_hits},
            branch_counts={name: len(hits) for name, hits in rankings.items()},
            terms=terms,
        )

    async def retrieve(
        self,
        query: str,
        filters: SearchFilters,
        *,
        limit: int = 10,
        max_per_document: int | None = None,
        branches: tuple[str, ...] = DEFAULT_BRANCHES,
        decompose_query: bool = False,
        reranker=None,
        rerank_candidates: int = DEFAULT_RERANK_CANDIDATES,
        index_penalty: float = DEFAULT_INDEX_PENALTY,
        dedupe_text: bool = DEFAULT_DEDUPE_TEXT,
    ) -> RetrievalResult:
        """The chunks relevant to ``query``, within ``filters``.

        With ``decompose_query`` a compound question is also asked in parts, and
        what the parts find is APPENDED to what the whole question found. The
        prefix is untouched on purpose -- see the class docstring of
        ``decomposition`` and §1 of that change's design: the two variants that
        reorder both broke documents the whole query already had, because RRF
        over sub-queries dilutes. Appending cannot regress by construction.

        || Con ``decompose_query`` una pregunta compuesta se pregunta además por
        partes, y lo que las partes encuentran se AGREGA a lo que encontró la
        pregunta entera. El prefijo no se toca a propósito: las dos variantes
        que reordenan rompieron documentos que la consulta completa ya tenía,
        porque RRF sobre subconsultas diluye. Agregar no puede regresar por
        construcción.

        With ``reranker`` the candidate set is widened to ``rerank_candidates``,
        reordered, and cut back to ``limit``. Widening is the point: reranking
        the same 10 the search already picked has nothing to work with, and the
        28 convertible pairs are precisely the ones between place 11 and 60.

        || Con ``reranker`` el candidato se ensancha a ``rerank_candidates``, se
        reordena y se recorta a ``limit``. Ensanchar es todo el punto: reordenar
        los mismos 10 que la búsqueda ya eligió no tiene con qué trabajar, y los
        28 pares convertibles son justamente los que están entre el puesto 11 y
        el 60.
        """
        whole = await self._fuse_branches(
            query, filters, branches,
            index_penalty=index_penalty, dedupe_text=dedupe_text,
        )
        fused, by_document = whole.fused, whole.by_document

        if decompose_query:
            fused, by_document = await self._append_sub_queries(
                query, filters, branches, fused, by_document,
                index_penalty=index_penalty, dedupe_text=dedupe_text,
            )

        # A reranker needs more than `limit` to reorder, so the cap is asked for
        # the wider set and the cut back to `limit` happens after reordering.
        # || Un reranker necesita más que `limit` para reordenar, así que el tope
        # se pide sobre el conjunto ancho y el recorte a `limit` pasa después de
        # reordenar.
        wanted = max(limit, rerank_candidates) if reranker is not None else limit
        capped = cap_per_group(
            fused,
            lambda content_hash: by_document.get(content_hash, content_hash),
            cap=max_per_document,
            limit=wanted,
        )

        # The branches carry different row shapes (a distance, a rank, a
        # constant), so the winners are rehydrated once instead of every branch
        # dragging the text along.
        # || Las ramas llevan formas de fila distintas (una distancia, un rank,
        # una constante), así que los ganadores se rehidratan una vez en lugar
        # de que cada rama arrastre el texto.
        hydrated = await self._repository.by_content_hashes(
            [item.key for item in capped], filters
        )

        chunks = []
        for item in capped:
            row = hydrated.get(item.key)
            if row is None:
                # The chunk was in a branch's result and not in the rehydration:
                # the corpus was reloaded mid-query. Skipping beats returning a
                # hit with no text.
                # || El chunk estaba en el resultado de una rama y no en la
                # rehidratación: el corpus se recargó entre medio. Saltearlo es
                # mejor que devolver un hit sin texto.
                logger.warning("retrieval_chunk_vanished", content_hash=item.key)
                continue
            chunks.append(
                RetrievedChunk(
                    content_hash=row.content_hash,
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    document_title=row.document_title,
                    section=row.section,
                    bullet_path=row.bullet_path,
                    module_code=row.module_code,
                    document_kind=row.document_kind,
                    text=row.text,
                    score=item.score,
                    branches=item.branches,
                    ranks=item.ranks,
                )
            )

        if reranker is not None:
            # Reordering happens on the HYDRATED chunks: a reranker judges by
            # title, section and text, and none of that exists before this
            # point.
            # || El reordenamiento va sobre los chunks HIDRATADOS: un reranker
            # juzga por título, sección y texto, y nada de eso existe antes de
            # este punto.
            chunks = reranker.rerank(query, chunks)[:limit]

        return RetrievalResult(
            chunks=chunks,
            # The WHOLE query's branches, never the sub-queries': this is what
            # the caller asked, and a count mixing both would report a branch
            # activity that no single query had.
            # || Las ramas de la consulta ENTERA, nunca las de las subconsultas:
            # es lo que preguntó quien llama, y un conteo que mezclara las dos
            # reportaría una actividad de rama que ninguna consulta tuvo.
            branch_counts=whole.branch_counts,
            identifier_terms=whole.terms,
        )

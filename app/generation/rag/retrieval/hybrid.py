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

from app.generation.rag.retrieval.fusion import (
    DEFAULT_RRF_K,
    cap_per_group,
    reciprocal_rank_fusion,
)
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

    async def retrieve(
        self,
        query: str,
        filters: SearchFilters,
        *,
        limit: int = 10,
        max_per_document: int | None = None,
        branches: tuple[str, ...] = DEFAULT_BRANCHES,
    ) -> RetrievalResult:
        """The chunks relevant to ``query``, within ``filters``.

        || Los chunks relevantes a ``query``, dentro de ``filters``.
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

        by_document = {
            hit.content_hash: hit.document_id for hits in rankings.values() for hit in hits
        }
        capped = cap_per_group(
            fused,
            lambda content_hash: by_document.get(content_hash, content_hash),
            cap=max_per_document,
            limit=limit,
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
                    text=row.text,
                    score=item.score,
                    branches=item.branches,
                    ranks=item.ranks,
                )
            )

        return RetrievalResult(
            chunks=chunks,
            branch_counts={name: len(hits) for name, hits in rankings.items()},
            identifier_terms=terms,
        )

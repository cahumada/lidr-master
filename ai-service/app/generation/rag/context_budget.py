"""Fit the retrieved evidence into a token budget before it becomes a prompt.

Nothing counted tokens before this module existed: ``build_context`` joined
every hit it was handed and the provider was the first thing to notice. The
effective size is not the caller's ``limit`` — the agentic path unions the
hits of every sub-query — so the overflow depends on the SHAPE of the
question, which is the hardest kind of failure to reproduce.

Three rules, each one deliberate (see the change's ``design.md``):

* **The count is an estimate, not accounting.** It uses the embedding
  model's tokenizer (:func:`count_tokens`), NOT the tokenizer of the model
  that answers — which, for a service that can synthesize through OpenAI,
  Anthropic or Moonshot, is not available locally at all. The default budget
  is roomy against the real windows precisely because that margin is what
  absorbs the tokenizer difference.
* **Whole chunks, from the tail.** A chunk is a functional unit of the
  source spec (Función/Efecto/Notas). Half a chunk is a truncated business
  rule that reads as a complete one, which in an insurance corpus is worse
  than one rule fewer.
* **Nothing is dropped in silence.** What did not fit is returned, counted
  and logged, because a chunk that never reached the prompt is business
  information lost for that answer.

|| Ajusta la evidencia recuperada a un presupuesto de tokens antes de que
sea un prompt.

Antes de este módulo nadie contaba tokens: ``build_context`` concatenaba
todos los hits que le pasaran y el proveedor era el primero en enterarse. El
tamaño efectivo no es el ``limit`` de quien llama —el camino agéntico une
los hits de cada subconsulta—, así que el desborde depende de la FORMA de la
pregunta, que es la peor clase de fallo para reproducir.

Tres reglas, cada una deliberada (ver el ``design.md`` del cambio): el
conteo es una ESTIMACIÓN con el tokenizer de los embeddings y no el del
modelo que responde; se descartan chunks ENTEROS desde la cola; y nada se
descarta en silencio.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import structlog

from app.generation.rag.chunking.base import count_tokens
from app.generation.rag.schemas import SearchHit

log = structlog.get_logger()


def render_hit_block(index: int, hit: SearchHit) -> str:
    """One numbered evidence block, provenance first.

    The single renderer for a hit: :func:`fit_to_budget` counts tokens over
    what this returns and ``build_context`` emits exactly this, so the text
    that was measured and the text the model receives cannot drift apart.
    The header and the breadcrumb are real tokens the model will read —
    counting only ``hit.text`` would under-report every block.

    || Un bloque de evidencia numerado, la procedencia primero. Es el ÚNICO
    renderer de un hit: :func:`fit_to_budget` cuenta tokens sobre lo que
    devuelve esta función y ``build_context`` emite exactamente esto, así el
    texto medido y el que recibe el modelo no pueden separarse. El
    encabezado y el breadcrumb son tokens reales — contar solo ``hit.text``
    subestimaría cada bloque.
    """
    section = hit.section or "(sin sección)"
    lines = [f"### {index}. [{hit.document_id} · {section}]"]
    if hit.document_title:
        lines.append(f"Documento: {hit.document_title}")
    if hit.bullet_path:
        lines.append(f"Ruta: {hit.bullet_path}")
    lines.append(hit.text)
    return "\n".join(lines)


@dataclass(frozen=True)
class BudgetedContext:
    """What fits, what did not, and what it cost.

    ``dropped`` is kept whole rather than as a count so the caller can log
    which documents were left out; the HTTP contract only carries the
    number, but the decision of what to do with the rest belongs upstream.

    || Lo que entra, lo que no, y cuánto costó. ``dropped`` se conserva
    entero y no como un número para que quien llama pueda registrar qué
    documentos quedaron afuera; el contrato HTTP solo lleva la cantidad.
    """

    kept: list[SearchHit]
    dropped: list[SearchHit]
    tokens_used: int
    budget: int

    @property
    def truncated(self) -> bool:
        """Whether anything was left out. || Si quedó algo afuera."""
        return bool(self.dropped)

    @property
    def dropped_count(self) -> int:
        """How many hits were left out. || Cuántos hits quedaron afuera."""
        return len(self.dropped)


def interleave_by_query(groups: Sequence[Sequence[SearchHit]]) -> list[SearchHit]:
    """Round-robin across the per-sub-query result lists, de-duplicated.

    With one group this is the identity: the retriever already returned that
    list best-first, and reordering a single ranked run would throw away the
    only ordering that means anything.

    With several, the naive concatenation has a concrete failure mode. For
    "¿qué valida CA014 y qué reporta CO001?", if the evidence for ``CA014``
    fills the budget, the evidence for ``CO001`` disappears ENTIRELY and the
    model answers half the question with full confidence. Interleaving makes
    the budget bite every sub-query a little instead of one of them
    completely.

    Sorting the union by ``score`` instead would look more principled and be
    wrong: RRF scores come from independent fusions, one per retrieval run,
    so two sub-queries' top hits score alike by construction rather than by
    comparable merit.

    A hit found by two sub-queries enters once, at the position of the first
    one that brought it.

    || Round-robin entre las listas de cada subconsulta, deduplicando. Con
    un solo grupo es la identidad. Con varios evita el modo de fallo de la
    concatenación: que una pregunta compuesta pierda entera la evidencia de
    su segunda mitad porque la primera llenó el presupuesto. Ordenar la
    unión por ``score`` sería incorrecto: los puntajes RRF vienen de
    fusiones independientes y no son comparables entre sí. Un hit que
    encontraron dos subconsultas entra una sola vez, en la posición de la
    primera que lo trajo.
    """
    ordered: list[SearchHit] = []
    seen: set[str] = set()
    depth = 0
    remaining = True
    while remaining:
        remaining = False
        for group in groups:
            if depth >= len(group):
                continue
            remaining = True
            hit = group[depth]
            key = hit.content_hash or hit.chunk_id
            if key in seen:
                continue
            seen.add(key)
            ordered.append(hit)
        depth += 1
    return ordered


def fit_to_budget(hits: Sequence[SearchHit], budget: int) -> BudgetedContext:
    """Keep the leading hits that fit in ``budget`` tokens.

    The walk stops at the FIRST hit that does not fit, instead of skipping
    it to squeeze in a smaller one further down. Continuing would fill the
    budget better and would silently promote a less relevant chunk over a
    more relevant one — the kept set would stop being "the best evidence"
    and become "the evidence that happened to be small".

    || Conserva los primeros hits que entran en ``budget`` tokens. El
    recorrido se detiene en el PRIMERO que no entra, en vez de saltearlo
    para meter uno más chico de más abajo: seguir llenaría mejor el
    presupuesto y ascendería en silencio un chunk menos relevante sobre uno
    más relevante.
    """
    kept: list[SearchHit] = []
    used = 0
    for index, hit in enumerate(hits, start=1):
        cost = count_tokens(render_hit_block(index, hit))
        if used + cost > budget:
            break
        kept.append(hit)
        used += cost

    dropped = list(hits[len(kept) :])
    if dropped:
        log.info(
            "answer_context_budgeted",
            hits_in=len(hits),
            hits_kept=len(kept),
            hits_dropped=len(dropped),
            tokens_used=used,
            budget=budget,
            dropped_document_ids=sorted({hit.document_id for hit in dropped}),
        )
    return BudgetedContext(kept=kept, dropped=dropped, tokens_used=used, budget=budget)

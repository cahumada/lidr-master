"""Build the RAG prompt from retrieved hits.

Each chunk enters with its provenance visible — document, section, breadcrumb
— not as bare text. The model can only cite what it can see, and a citation
without a document_id next to the chunk is an invitation to invent one.

|| Arma el prompt de RAG a partir de los hits recuperados. Cada chunk entra
con su procedencia visible —documento, sección, breadcrumb— no como texto
pelado. El modelo solo puede citar lo que ve, y una cita sin document_id al
lado del chunk es una invitación a inventar uno.
"""

from __future__ import annotations

from collections.abc import Callable

from app.foundation.prompts import render_prompt
from app.generation.rag.context_budget import (
    BudgetedContext,
    fit_to_budget,
    render_hit_block,
)
from app.generation.rag.schemas import SearchHit

PROMPT_NAME = "answer"
PROMPT_VERSION = "v1"

# The version that carries the conversation-memory block. A run WITHOUT memory
# keeps rendering `v1`, byte for byte: an answer produced with memory is not
# comparable to one produced without it, and the fidelity eval has to be able
# to tell two runs apart by more than a hope. Same reason the prompts were
# versioned from the start rather than edited in place.
# || La versión que lleva el bloque de memoria de conversación. Una corrida SIN
# memoria sigue renderizando `v1`, byte a byte: una respuesta producida con
# memoria no es comparable con una producida sin ella, y el eval de fidelidad
# tiene que poder distinguir dos corridas por algo más que una esperanza.
PROMPT_VERSION_WITH_MEMORY = "v2"


def build_context(hits: list[SearchHit]) -> str:
    """One numbered block per hit, provenance first.

    The per-hit rendering lives in :func:`render_hit_block`, which is also
    what the token budget measures. One renderer, so the text that was
    counted and the text that is sent cannot drift apart.

    || Un bloque numerado por hit, la procedencia primero. El renderizado de
    cada hit vive en :func:`render_hit_block`, que es lo mismo que mide el
    presupuesto de tokens: un solo renderer, así el texto contado y el
    enviado no pueden separarse.
    """
    return "\n\n".join(
        render_hit_block(index, hit) for index, hit in enumerate(hits, start=1)
    )


def build_messages(
    question: str,
    hits: list[SearchHit],
    *,
    persona: str | None = None,
    guardrails: str | None = None,
    memory: str | None = None,
) -> tuple[str, str]:
    """Render the versioned system + user pair for this question.

    ``persona`` and ``guardrails`` come from the ``answer_synthesizer``
    profile and are appended after the rules — subordinate to them on
    purpose. A persona changes the voice; operator guardrails add
    constraints. Neither should be able to talk the model out of citing
    its sources.

    ``memory`` is the conversation block, and it enters LAST — after the
    persona, before the retrieved context — with the same subordination and
    one addition of its own: it is explicitly not provenance. What an earlier
    turn cited does not back this answer.

    Without ``memory`` this renders ``v1`` exactly as before; with it, ``v2``.

    || Renderiza el par system + user versionado para esta pregunta.
    ``persona`` y ``guardrails`` salen del perfil y se appendean después de
    las reglas, subordinados a ellas. ``memory`` es el bloque de conversación
    y entra ÚLTIMO, con la misma subordinación más una propia: explícitamente
    no es procedencia. Sin ``memory`` renderiza ``v1`` igual que antes; con
    ella, ``v2``.
    """
    version = PROMPT_VERSION_WITH_MEMORY if memory else PROMPT_VERSION
    system_values: dict[str, object] = {"persona": persona, "guardrails": guardrails}
    if memory:
        system_values["memory"] = memory

    system = render_prompt(PROMPT_NAME, version, "system", **system_values)
    user = render_prompt(
        PROMPT_NAME,
        version,
        "user",
        question=question,
        context=build_context(hits),
    )
    return system, user


def build_budgeted_messages(
    question: str,
    hits: list[SearchHit],
    *,
    budget: int,
    persona: str | None = None,
    guardrails: str | None = None,
    memory_for: Callable[[int], str | None] | None = None,
) -> tuple[str, str, BudgetedContext]:
    """Fit the evidence to ``budget``, then render the prompt from what fit.

    The composed entry point every synthesis path uses. It exists so that no
    caller can render a prompt and forget the budget: :func:`build_messages`
    stays the raw renderer for whoever already decided what to send.

    The returned :class:`BudgetedContext` is not a diagnostic — the caller
    needs it. ``kept`` is what the answer may cite (a chunk that never
    reached the prompt backs nothing), and ``dropped`` is what has to be
    reported so the trim is visible rather than silent.

    ``memory_for`` is called with the tokens the evidence left unused and
    returns the conversation-memory block, or ``None``. A callable rather
    than a string because the ORDER matters: evidence is fitted first and
    memory takes the remainder, never the other way round.

    || Ajusta la evidencia a ``budget`` y arma el prompt con lo que entró.
    Es el punto de entrada que usa cada camino de síntesis, para que nadie
    pueda renderizar un prompt y olvidarse del presupuesto. El
    :class:`BudgetedContext` que devuelve no es un diagnóstico: ``kept`` es
    lo que la respuesta puede citar —un chunk que nunca llegó al prompt no
    respalda nada— y ``dropped`` es lo que hay que reportar para que el
    recorte se vea en vez de pasar en silencio.
    """
    # Evidence is fitted FIRST, against the whole budget; the conversation
    # memory then gets whatever is left. That order is the invariant, and it
    # lives here rather than in the caller so it cannot be got wrong one call
    # site at a time: memory can never take budget away from a chunk.
    # || La evidencia se ajusta PRIMERO contra el presupuesto entero; la
    # memoria se queda con lo que sobre. Ese orden es el invariante y vive acá
    # y no en quien llama, para que no se pueda equivocar de a un call site por
    # vez: la memoria nunca puede sacarle presupuesto a un chunk.
    budgeted = fit_to_budget(hits, budget)
    memory = memory_for(budget - budgeted.tokens_used) if memory_for else None
    system, user = build_messages(
        question,
        budgeted.kept,
        persona=persona,
        guardrails=guardrails,
        memory=memory,
    )
    return system, user, budgeted

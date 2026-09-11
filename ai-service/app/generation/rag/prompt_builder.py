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

from collections.abc import Callable, Sequence

from app.foundation.prompts import render_prompt
from app.generation.rag.business_db.models import BusinessDbContext
from app.generation.rag.business_db.render import block_text
from app.generation.rag.chunking.base import count_tokens
from app.generation.rag.context_budget import (
    BudgetedContext,
    StatusResolver,
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

# The version that carries the business-db block. A run WITHOUT the block
# keeps rendering `v1` or `v2` byte for byte — `v3` without the block is
# tested to match `v2`, so an accidental edit of one and not the other is
# visible. A run WITH the block is `v3` whether or not there is memory.
# || La versión que lleva el bloque de la base. Una corrida SIN el bloque
# sigue renderizando `v1` o `v2` byte a byte.
PROMPT_VERSION_WITH_BUSINESS_DB = "v3"

BusinessDbFor = Callable[[Sequence[SearchHit], int], BusinessDbContext | None]


def build_context(
    hits: list[SearchHit], *, status_of: StatusResolver | None = None
) -> str:
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
        render_hit_block(index, hit, status_of=status_of)
        for index, hit in enumerate(hits, start=1)
    )


def build_messages(
    question: str,
    hits: list[SearchHit],
    *,
    persona: str | None = None,
    guardrails: str | None = None,
    memory: str | None = None,
    business_db: str | None = None,
    status_of: StatusResolver | None = None,
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

    Without ``memory`` this renders ``v1`` exactly as before; with it and
    without ``business_db``, ``v2``; with ``business_db``, ``v3``.

    || Renderiza el par system + user versionado para esta pregunta.
    ``persona`` y ``guardrails`` salen del perfil y se appendean después de
    las reglas, subordinados a ellas. ``memory`` es el bloque de conversación
    y entra ÚLTIMO entre los opcionales viejos, con la misma subordinación
    más una propia: explícitamente no es procedencia. ``business_db`` es otra
    autoridad y elige ``v3``. Sin ``memory`` renderiza ``v1``; con ella y
    sin base, ``v2``.
    """
    if business_db:
        version = PROMPT_VERSION_WITH_BUSINESS_DB
    elif memory:
        version = PROMPT_VERSION_WITH_MEMORY
    else:
        version = PROMPT_VERSION
    system_values: dict[str, object] = {"persona": persona, "guardrails": guardrails}
    if memory:
        system_values["memory"] = memory
    if business_db:
        system_values["business_db"] = business_db

    system = render_prompt(PROMPT_NAME, version, "system", **system_values)
    user = render_prompt(
        PROMPT_NAME,
        version,
        "user",
        question=question,
        context=build_context(hits, status_of=status_of),
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
    business_db_for: BusinessDbFor | None = None,
    status_of: StatusResolver | None = None,
) -> tuple[str, str, BudgetedContext, BusinessDbContext | None]:
    """Fit the evidence to ``budget``, then render the prompt from what fit.

    The composed entry point every synthesis path uses. It exists so that no
    caller can render a prompt and forget the budget: :func:`build_messages`
    stays the raw renderer for whoever already decided what to send.

    The returned :class:`BudgetedContext` is not a diagnostic — the caller
    needs it. ``kept`` is what the answer may cite (a chunk that never
    reached the prompt backs nothing), and ``dropped`` is what has to be
    reported so the trim is visible rather than silent.

    ``memory_for`` is called with the tokens the evidence left unused and
    returns the conversation-memory block, or ``None``. ``business_db_for``
    is called after that, with the kept hits and whatever is still unused.
    Callables rather than strings because the ORDER is the invariant:
    evidence → memory → base. None of the later blocks can take budget
    away from an earlier one. That order lives here so no call site can
    get it wrong one at a time.

    || Ajusta la evidencia a ``budget`` y arma el prompt con lo que entró.
    Es el punto de entrada que usa cada camino de síntesis, para que nadie
    pueda renderizar un prompt y olvidarse del presupuesto. El orden de
    ajuste es evidencia → memoria → base, y vive acá.
    """
    # Evidence first against the whole budget; memory takes the remainder;
    # the business-db block takes what is still left. The base block is last
    # because it is the only one that can declare its own trim inside itself.
    # || La evidencia primero; la memoria se queda con lo que sobre; la base,
    # con lo que quede. La base va última porque es la única que puede
    # declarar adentro suyo lo que perdió.
    budgeted = fit_to_budget(hits, budget, status_of=status_of)
    remaining = budget - budgeted.tokens_used
    memory = memory_for(remaining) if memory_for else None
    if memory:
        remaining -= count_tokens(memory)
    db_context = business_db_for(budgeted.kept, remaining) if business_db_for else None
    db_text = block_text(db_context) if db_context is not None else None
    system, user = build_messages(
        question,
        budgeted.kept,
        persona=persona,
        guardrails=guardrails,
        memory=memory,
        business_db=db_text,
        status_of=status_of,
    )
    return system, user, budgeted, db_context

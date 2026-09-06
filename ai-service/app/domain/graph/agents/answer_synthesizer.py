"""Answer synthesis agent — reuses prompt_builder and get_answer_llm(), zero tools.

|| Agente de síntesis — reusa prompt_builder y get_answer_llm(), cero tools.
"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

import structlog
from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.domain.graph.privilege import record_model_action
from app.domain.schemas import AnswerAgentState
from app.generation.conversation.budget import render_memory
from app.generation.conversation.models import (
    Anchor,
    ConversationFacts,
    ConversationSession,
    Turn,
)
from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE
from app.generation.rag.prompt_builder import build_budgeted_messages
from app.generation.rag.schemas import SearchHit

log = structlog.get_logger()


def _memory_for(state: AnswerAgentState, settings) -> Callable[[int], str | None] | None:
    """A renderer for the conversation block, or ``None`` with no session.

    Returning ``None`` — rather than a callable that yields an empty string —
    is what keeps a run without a session rendering prompt ``v1`` byte for
    byte, so the fidelity eval can still compare it against every earlier run.

    The callable receives the tokens the evidence left unused and gives the
    memory the smaller of that and its own ceiling. Evidence has already been
    fitted by then; memory can only occupy what was going to be empty.

    || Un renderer del bloque de conversación, o ``None`` si no hay sesión.
    Devolver ``None`` —y no un callable que produce vacío— es lo que mantiene
    una corrida sin sesión renderizando el prompt ``v1`` byte a byte, así el
    eval de fidelidad la sigue pudiendo comparar contra las anteriores. El
    callable recibe los tokens que la evidencia dejó libres y le da a la
    memoria el menor entre eso y su propio techo.
    """
    if not state.get("session_id"):
        return None

    session = ConversationSession(
        session_id=str(state.get("session_id")),
        facts=ConversationFacts.model_validate(state.get("conversation_facts") or {}),
        anchors=[
            Anchor.model_validate(item) for item in (state.get("conversation_anchors") or [])
        ],
        turns=[Turn.model_validate(item) for item in (state.get("conversation_turns") or [])],
    )

    def _render(remaining: int) -> str | None:
        allowance = min(settings.CONVERSATION_MEMORY_MAX_TOKENS, max(remaining, 0))
        block = render_memory(session, budget=allowance)
        return block.text if block else None

    return _render


async def answer_synthesizer(state: AnswerAgentState, config: RunnableConfig) -> dict:
    """Generate a cited answer from retrieved hits.

    || Genera una respuesta citada a partir de los hits recuperados.
    """
    deps = (config.get("configurable") or {}) if config else {}
    llm = deps.get("llm")
    if llm is None:
        raise RuntimeError("answer_synthesizer requires configurable.llm")
    # From this agent's profile, when one is configured. Injected and not read
    # from the database here, so this stays testable without one.
    # || Del perfil de este agente, cuando hay uno configurado. Inyectada y no
    # leída de la base acá, así esto sigue siendo testeable sin base.
    persona = deps.get("persona")
    guardrails = deps.get("guardrails")

    step = int(state.get("supervisor_steps") or 0)
    # The question that was actually retrieved. Answering the written one
    # while citing evidence found for the resolved one is how a session
    # produces a well-cited answer to the wrong question.
    # || La pregunta que realmente se buscó. Responder la escrita citando
    # evidencia hallada para la resuelta es como una sesión produce una
    # respuesta bien citada a la pregunta equivocada.
    query = state.get("resolved_question") or state.get("query") or ""
    hits = [SearchHit.model_validate(hit) for hit in (state.get("hits") or [])]
    was_resynthesis = bool(state.get("pending_resynthesis"))

    if not hits:
        contribution = record_model_action(
            "answer_synthesizer",
            "insufficient_context",
            step=step,
            summary="no hits; skipped LLM",
        )
        log.info("agent_answer_synthesizer_empty", query=query)
        return {
            "answer": INSUFFICIENT_CONTEXT_MESSAGE,
            "citations": [],
            "context_truncated": False,
            "dropped_hits": 0,
            "agent_contributions": [contribution],
        }

    started = perf_counter()
    settings = get_settings()
    system, user, budgeted = build_budgeted_messages(
        query,
        hits,
        budget=settings.ANSWER_MAX_CONTEXT_TOKENS,
        persona=persona,
        guardrails=guardrails,
        memory_for=_memory_for(state, settings),
    )

    # Evidence came back and none of it fit the budget. Same outcome as no
    # hits -- nothing to ground on, no LLM call -- but `dropped_hits` keeps
    # the two distinguishable downstream.
    # || Vino evidencia y no entró ninguna en el presupuesto. Mismo desenlace
    # que sin hits —nada con qué anclar, no se llama al LLM— pero
    # `dropped_hits` mantiene los dos casos distinguibles aguas abajo.
    if not budgeted.kept:
        contribution = record_model_action(
            "answer_synthesizer",
            "insufficient_context",
            step=step,
            summary=f"{len(hits)} hits, none fit the {budgeted.budget}-token budget; skipped LLM",
        )
        log.warning(
            "agent_answer_synthesizer_budget_exhausted",
            query=query,
            hits=len(hits),
            budget=budgeted.budget,
        )
        return {
            "answer": INSUFFICIENT_CONTEXT_MESSAGE,
            "citations": [],
            "context_truncated": True,
            "dropped_hits": budgeted.dropped_count,
            "agent_contributions": [contribution],
        }

    answer = llm.complete(system=system, user=user)
    contribution = record_model_action(
        "answer_synthesizer",
        "synthesize_answer",
        step=step,
        summary=(
            f"answer over {len(budgeted.kept)} of {len(hits)} hits"
            f" · {getattr(llm, 'model', '?')}"
            f"{f' · {budgeted.dropped_count} dropped by budget' if budgeted.truncated else ''}"
            f"{' · persona' if persona else ''}"
            f"{' · guardrails' if guardrails else ''}"
        ),
        duration_ms=int((perf_counter() - started) * 1000),
    )
    log.info(
        "agent_answer_synthesizer",
        hits=len(budgeted.kept),
        dropped=budgeted.dropped_count,
        answer_chars=len(answer),
        model=getattr(llm, "model", None),
        persona_chars=len(persona or ""),
        guardrails_chars=len(guardrails or ""),
    )
    return {
        "answer": answer,
        # What the model was shown, not everything the retriever found: a
        # chunk that never reached the prompt is not provenance.
        # || Lo que vio el modelo, no todo lo que encontró el retriever: un
        # chunk que nunca llegó al prompt no es procedencia.
        "citations": [hit.model_dump() for hit in budgeted.kept],
        "context_truncated": budgeted.truncated,
        "dropped_hits": budgeted.dropped_count,
        "pending_resynthesis": False,
        "pending_revalidation": was_resynthesis,
        "agent_contributions": [contribution],
    }

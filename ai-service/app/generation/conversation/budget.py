"""Render the memory block, and trim it before it can crowd out evidence.

The discard order is the whole point of this module, and it is the opposite
of what a general-purpose chat would do. There, the conversation IS the
product and the retrieved context is a garnish. Here the product is a cited
answer: a turn pushed out of the prompt costs a repeated sentence, a chunk
pushed out costs a citation. They are not comparable, so the order is
explicit rather than left to whatever got concatenated first.

Turns go first, anchors second, facts never. Facts are ~200 tokens of
structured fields, they are what repairs the NEXT turn's retrieval, and they
were already used before the synthesizer ran.

The memory block is measured with the same estimate the evidence is
(:func:`count_tokens` — the embedding model's tokenizer, not the answering
model's) and is charged INSIDE the context budget, never on top of it.

|| Renderiza el bloque de memoria y lo recorta antes de que le saque lugar a
la evidencia.

El orden de descarte es el punto de este módulo, y es lo contrario de lo que
haría un chat genérico: allá la conversación ES el producto. Acá el producto
es una respuesta citada — un turno desplazado cuesta una frase repetida, un
chunk desplazado cuesta una cita. No son comparables, así que el orden es
explícito: primero los turnos, después los anchors, los hechos nunca.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.generation.conversation.models import ConversationSession
from app.generation.rag.chunking.base import count_tokens

log = structlog.get_logger()


@dataclass(frozen=True)
class MemoryBlock:
    """The rendered memory and what had to be left out to fit it.

    || La memoria renderizada y qué hubo que dejar afuera para que entrara.
    """

    text: str
    turns_included: int
    turns_dropped: int
    anchors_included: int
    anchors_dropped: int
    tokens_used: int

    @property
    def trimmed(self) -> bool:
        """Whether anything was left out. || Si quedó algo afuera."""
        return bool(self.turns_dropped or self.anchors_dropped)


def _facts_lines(session: ConversationSession) -> list[str]:
    facts = session.facts
    lines: list[str] = []
    if facts.module_code:
        lines.append(f"- Módulos en juego: {', '.join(facts.module_code)}")
    if facts.window_type_name:
        lines.append(f"- Tipos de ventana en juego: {', '.join(facts.window_type_name)}")
    if facts.transaction_codes:
        lines.append(f"- Transacciones mencionadas: {', '.join(facts.transaction_codes)}")
    if facts.last_document_ids:
        lines.append(
            f"- La respuesta anterior citó: {', '.join(facts.last_document_ids)}"
        )
    return lines


def _anchor_line(kind: str, value: str) -> str:
    label = "módulo" if kind == "module_code" else "tipo de ventana"
    return f"- El usuario fijó {label}: {value}"


def _turn_lines(index: int, question: str, answer: str) -> list[str]:
    return [f"- Turno {index}:", f"  Pregunta: {question}", f"  Respuesta: {answer}"]


def render_memory(
    session: ConversationSession | None,
    *,
    budget: int,
    answer_preview_chars: int = 400,
) -> MemoryBlock | None:
    """Render what the model should remember, trimmed to ``budget`` tokens.

    Returns ``None`` when there is nothing to remember, so the caller can tell
    "no memory" from "an empty memory block" and keep the no-session path
    byte-identical to what it was before sessions existed.

    Turns are dropped OLDEST first: the last exchange is the one a follow-up
    is most likely leaning on.

    || Renderiza lo que el modelo debería recordar, recortado a ``budget``
    tokens. Devuelve ``None`` cuando no hay nada que recordar, así quien llama
    distingue «sin memoria» de «bloque de memoria vacío» y el camino sin
    sesión queda idéntico al de antes. Los turnos se descartan del MÁS VIEJO
    primero: el último intercambio es en el que más probablemente se apoya una
    pregunta de seguimiento.
    """
    if session is None:
        return None

    facts_lines = _facts_lines(session)
    if not (facts_lines or session.anchors or session.turns):
        return None

    header = "Memoria de la conversación (contexto, NUNCA procedencia: citá solo el contexto recuperado):"

    def _render(anchors: list, turns: list) -> str:
        lines = [header]
        lines.extend(facts_lines)
        lines.extend(_anchor_line(anchor.kind, anchor.value) for anchor in anchors)
        for index, turn in enumerate(turns, start=1):
            lines.extend(
                _turn_lines(
                    index,
                    turn.resolved_question,
                    turn.answer[:answer_preview_chars],
                )
            )
        return "\n".join(lines)

    anchors = list(session.anchors)
    turns = list(session.turns)
    turns_dropped = 0
    anchors_dropped = 0

    # Oldest turns first, then anchors, then whatever the facts alone cost --
    # which is emitted even over budget, because the alternative is a session
    # that silently forgets the one thing it must not.
    # || Primero los turnos más viejos, después los anchors, y al final lo que
    # cuesten los hechos solos —que se emiten aunque excedan, porque la
    # alternativa es una sesión que olvida en silencio lo único que no debe.
    while turns and count_tokens(_render(anchors, turns)) > budget:
        turns.pop(0)
        turns_dropped += 1
    while anchors and count_tokens(_render(anchors, turns)) > budget:
        anchors.pop(0)
        anchors_dropped += 1

    text = _render(anchors, turns)
    used = count_tokens(text)
    if turns_dropped or anchors_dropped:
        log.info(
            "conversation_memory_trimmed",
            session_id=session.session_id,
            turns_dropped=turns_dropped,
            anchors_dropped=anchors_dropped,
            tokens_used=used,
            budget=budget,
        )
    return MemoryBlock(
        text=text,
        turns_included=len(turns),
        turns_dropped=turns_dropped,
        anchors_included=len(anchors),
        anchors_dropped=anchors_dropped,
        tokens_used=used,
    )

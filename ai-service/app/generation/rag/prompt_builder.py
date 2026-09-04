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

from app.foundation.prompts import render_prompt
from app.generation.rag.schemas import SearchHit

PROMPT_NAME = "answer"
PROMPT_VERSION = "v1"


def build_context(hits: list[SearchHit]) -> str:
    """One numbered block per hit, provenance first.

    || Un bloque numerado por hit, la procedencia primero.
    """
    blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        section = hit.section or "(sin sección)"
        header = f"[{hit.document_id} · {section}]"
        lines = [f"### {index}. {header}"]
        if hit.document_title:
            lines.append(f"Documento: {hit.document_title}")
        if hit.bullet_path:
            lines.append(f"Ruta: {hit.bullet_path}")
        lines.append(hit.text)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_messages(
    question: str, hits: list[SearchHit], *, persona: str | None = None
) -> tuple[str, str]:
    """Render the versioned system + user pair for this question.

    ``persona`` is the ``answer_synthesizer`` profile's text, appended to the
    system prompt after the rules — subordinate to them on purpose: a persona
    is meant to change the voice, and no configuration should be able to talk
    the model out of citing its sources.

    || Renderiza el par system + user versionado para esta pregunta.
    ``persona`` es el texto del perfil de ``answer_synthesizer``, appendeado al
    system prompt después de las reglas y subordinado a ellas a propósito: una
    persona cambia la voz, y ninguna configuración debería poder convencer al
    modelo de no citar sus fuentes.
    """
    system = render_prompt(PROMPT_NAME, PROMPT_VERSION, "system", persona=persona)
    user = render_prompt(
        PROMPT_NAME,
        PROMPT_VERSION,
        "user",
        question=question,
        context=build_context(hits),
    )
    return system, user

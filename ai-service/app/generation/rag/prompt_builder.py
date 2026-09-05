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
    question: str,
    hits: list[SearchHit],
    *,
    persona: str | None = None,
    guardrails: str | None = None,
) -> tuple[str, str]:
    """Render the versioned system + user pair for this question.

    ``persona`` and ``guardrails`` come from the ``answer_synthesizer``
    profile and are appended after the rules — subordinate to them on
    purpose. A persona changes the voice; operator guardrails add
    constraints. Neither should be able to talk the model out of citing
    its sources.

    || Renderiza el par system + user versionado para esta pregunta.
    ``persona`` y ``guardrails`` salen del perfil y se appendean después
    de las reglas, subordinados a ellas.
    """
    system = render_prompt(
        PROMPT_NAME,
        PROMPT_VERSION,
        "system",
        persona=persona,
        guardrails=guardrails,
    )
    user = render_prompt(
        PROMPT_NAME,
        PROMPT_VERSION,
        "user",
        question=question,
        context=build_context(hits),
    )
    return system, user

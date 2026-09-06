"""Derive the session's facts from what the turn already produced.

The course runs a second LLM call per turn to extract its ``ProjectMetadata``,
and has to: project name, team size and agreed scope are things a person
SAID, recoverable only by reading the prose.

Nothing here needs reading. The filters are the ones the retriever was handed,
the citations are the hits that reached the prompt, and a transaction code is
a token with a fixed shape. Paying for a completion to re-derive values the
pipeline already holds would buy latency and a new failure mode, and nothing
else.

|| Deriva los hechos de la sesión de lo que el turno ya produjo.

El curso corre una segunda llamada LLM por turno para extraer su
``ProjectMetadata``, y no le queda otra: el nombre del proyecto, el tamaño del
equipo y el scope acordado son cosas que alguien DIJO, recuperables solo
leyendo la prosa. Acá no hay nada que leer: los filtros son los que recibió el
retriever, las citas son los hits que llegaron al prompt, y un código de
transacción es un token con forma fija. Pagar una completion para re-derivar
valores que el pipeline ya tiene compraría latencia y un modo de falla nuevo,
nada más.
"""

from __future__ import annotations

import re

from app.generation.conversation.models import ConversationFacts

_TRANSACTION_TOKEN = re.compile(r"\b[A-Za-z]{2,4}\d{2,}[A-Za-z0-9_]*\b")


def codes_in(text: str) -> list[str]:
    """Transaction-shaped tokens in ``text``, upper-cased, first-seen order.

    || Tokens con forma de transacción en ``text``, en mayúsculas y en orden
    de aparición.
    """
    found: list[str] = []
    seen: set[str] = set()
    for match in _TRANSACTION_TOKEN.finditer(text or ""):
        code = match.group(0).upper()
        if code not in seen:
            seen.add(code)
            found.append(code)
    return found


def facts_from_turn(
    *,
    question: str,
    filters: dict[str, list[str]] | None,
    cited_document_ids: list[str],
) -> ConversationFacts:
    """The facts this one turn establishes, before merging with the session's.

    ``cited_document_ids`` are the documents the answer was built from — the
    budgeted hits, not everything the retriever found. A document the model
    never saw is not something the conversation learned.

    || Los hechos que establece este turno, antes de mergear con los de la
    sesión. ``cited_document_ids`` son los documentos con los que se armó la
    respuesta —los hits presupuestados, no todo lo que encontró el retriever—:
    un documento que el modelo nunca vio no es algo que la conversación sepa.
    """
    hints = filters or {}
    return ConversationFacts(
        module_code=list(hints.get("module_code") or []),
        window_type_name=list(hints.get("window_type_name") or []),
        transaction_codes=_union_preserving(codes_in(question), cited_document_ids),
        last_document_ids=list(cited_document_ids),
    )


def _union_preserving(first: list[str], second: list[str]) -> list[str]:
    merged = list(first)
    seen = {value.casefold() for value in merged}
    for value in second:
        if value.casefold() not in seen:
            merged.append(value)
            seen.add(value.casefold())
    return merged

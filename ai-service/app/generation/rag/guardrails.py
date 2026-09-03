"""Output guardrail for generated answers.

Input validation is NOT duplicated here. ``AnswerRequest.question`` carries
``Field(min_length=2)``, the same rule ``GET /search`` already enforces with
``Query(min_length=2)``. A one-character query cannot retrieve anything useful
and costs as much as a real one — that is the whole rule, and stating it in a
second function would let the two copies drift. Generation adds no extra input
check because retrieval already refuses the queries that cannot produce
context.

The output check is the hallucination that matters in this domain: a
``document_id`` cited in the prose that was not in the retrieved hits. The
model can invent a citation marker as easily as a fake transaction code;
comparing against the hits — not against what the model claims it cited — is
the only check that is verifiable.

Marks (``grounded=false``), does not reject: ``citations`` on the response
*is* the verifiable provenance (the retrieved ``SearchHit``s). An HTTP 4xx
would hide a usable answer and make the fidelity eval unable to score it.

|| Guardrail de salida para las respuestas generadas. La validación de
entrada NO se duplica acá. ``AnswerRequest.question`` lleva
``Field(min_length=2)``, la misma regla que ``GET /search`` ya impone con
``Query(min_length=2)``. Una consulta de un carácter no puede recuperar nada
útil y cuesta lo mismo que una real — esa es toda la regla, y escribirla en
una segunda función dejaría que las dos copias divergieran. La generación no
agrega ningún chequeo de entrada extra porque la recuperación ya rechaza las
consultas que no pueden producir contexto.

El chequeo de salida es la alucinación que importa en este dominio: un
``document_id`` citado en la prosa que no estaba en los hits recuperados. El
modelo puede inventar un marcador de cita igual de fácil que un código de
transacción falso; comparar contra los hits —no contra lo que el modelo diga
que citó— es el único chequeo verificable.

Marca (``grounded=false``), no rechaza: ``citations`` en la respuesta *es* la
procedencia verificable (los ``SearchHit`` recuperados). Un 4xx escondería
una respuesta usable e impediría puntuarla en el eval de fidelidad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.generation.rag.schemas import SearchHit

# The format the system prompt demands. The middle dot is the separator the
# prompt names; `|` and dashes are accepted because models drift on
# punctuation and a drifted citation of a real document is still a citation.
# || El formato que exige el system prompt. El punto medio es el separador
# que nombra el prompt; se aceptan `|` y rayas porque los modelos se desvían
# en la puntuación y una cita desviada de un documento real sigue siendo una
# cita.
CITATION_PATTERN = re.compile(
    r"\[([A-Za-z][A-Za-z0-9_-]*)\s*[·|–—-]\s*([^\]]+)\]"
)


@dataclass(frozen=True)
class GroundingResult:
    """Outcome of the output guardrail. || Resultado del guardrail de salida."""

    grounded: bool
    cited_document_ids: list[str] = field(default_factory=list)
    unsupported_document_ids: list[str] = field(default_factory=list)


def extract_cited_document_ids(answer: str) -> list[str]:
    """Document ids the prose marked as citations, order preserved, de-duplicated.

    || Ids de documento que la prosa marcó como citas, en orden y sin duplicar.
    """
    seen: set[str] = set()
    cited: list[str] = []
    for match in CITATION_PATTERN.finditer(answer):
        document_id = match.group(1)
        key = document_id.casefold()
        if key in seen:
            continue
        seen.add(key)
        cited.append(document_id)
    return cited


def citations_cover_expected(citation_ids: list[str], expected: set[str]) -> bool:
    """True when at least one expected document is among the citations.

    The fidelity predicate the eval reports as ``citation_coverage``. Lives
    here so the script and the tests cannot disagree on what "covered" means.

    || True cuando al menos un documento esperado está entre las citas. El
    predicado de fidelidad que el eval reporta como ``citation_coverage``.
    Vive acá para que el script y los tests no puedan disentir en qué es
    "cubierto".
    """
    cited = {document_id.casefold() for document_id in citation_ids}
    return any(document_id.casefold() in cited for document_id in expected)


def check_grounding(answer: str, hits: list[SearchHit]) -> GroundingResult:
    """Whether every inline citation names a retrieved document.

    An answer with no citation markers is grounded: inventing a document_id
    is the failure mode this checks, not failing to cite. Missing citations
    are a prompt-compliance issue, not a hallucination of provenance.

    || Si cada cita inline nombra un documento recuperado. Una respuesta sin
    marcadores está grounded: inventar un document_id es el modo de falla que
    esto chequea, no dejar de citar. Las citas faltantes son un tema de
    cumplimiento del prompt, no una alucinación de procedencia.
    """
    retrieved = {hit.document_id.casefold() for hit in hits if hit.document_id}
    cited = extract_cited_document_ids(answer)
    unsupported = [
        document_id for document_id in cited if document_id.casefold() not in retrieved
    ]
    return GroundingResult(
        grounded=not unsupported,
        cited_document_ids=cited,
        unsupported_document_ids=unsupported,
    )

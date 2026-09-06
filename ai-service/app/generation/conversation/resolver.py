"""Turn a referential question into a retrievable one, before retrieval runs.

This is the piece the course's conversational estimator does not need and the
reason this change exists. There, history enters the generation call and the
job is done. Here, "¿y para siniestros?" reaches `evidence_retriever` as loose
text, matches whatever looks like it, and the synthesizer writes a
well-cited answer to a question nobody asked — which in an insurance corpus is
worse than an error, because it arrives with verifiable provenance attached.

Deterministic and conservative, in that order. The risk this module
introduces is real: a resolver that expands toward the wrong referent
produces a wrong search with MORE confidence than the broken question did,
because it now looks well-formed. Three things hold that down:

1. A question that names its own subject is never rewritten.
2. With no referent in the facts, the question is returned untouched.
3. What was substituted travels in the result, so a wrong expansion is
   visible in the response instead of being discovered through a subtly
   wrong answer.

|| Convierte una pregunta referencial en una que se pueda buscar, antes de la
recuperación. Es la pieza que el estimador conversacional del curso no
necesita y el motivo de este cambio.

Determinista y conservador, en ese orden. El riesgo que introduce es real: un
resolver que expande hacia el referente equivocado produce una búsqueda
equivocada con MÁS confianza que la pregunta rota, porque ahora parece bien
formada. Lo sujetan tres cosas: una pregunta que nombra su propio sujeto no se
reescribe nunca; sin referente en los hechos se devuelve tal cual; y lo
sustituido viaja en el resultado, así una expansión equivocada se ve en la
respuesta en vez de descubrirse por una respuesta sutilmente mal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from app.generation.conversation.models import ConversationFacts

log = structlog.get_logger()

# How many referents a rewrite may name. Two keeps the question readable; the
# whole citation list of the previous answer would bury the actual question.
# || Cuántos referentes puede nombrar una reescritura. Dos mantiene la
# pregunta legible; toda la lista de citas de la respuesta anterior taparía la
# pregunta misma.
MAX_REFERENTS = 2

# A transaction-shaped token: two to four letters followed by digits (CA014,
# CO001_A). A question carrying one already names its subject.
# || Token con forma de transacción. Una pregunta que lleva uno ya nombra su
# sujeto.
_TRANSACTION_TOKEN = re.compile(r"\b[A-Za-z]{2,4}\d{2,}[A-Za-z0-9_]*\b")

# Markers that a question is leaning on the previous turn.
#
# The distinction that matters is DETERMINER vs PRONOUN, and getting it wrong
# was measured rather than imagined: an earlier version matched `esa|ese|esos`
# anywhere and fired on 3 of the 35 golden questions — "esos boletines", "esa
# cobranza", "ese pago". Every one of those names its own subject; the
# demonstrative is modifying a noun, not standing in for something said
# before. Rewriting them would have appended a referent to a question that
# already had one, which is exactly the failure `design.md` section 6 warns
# about: a wrong search that looks better formed than the original.
#
# So the gendered demonstratives count only when nothing follows them — end of
# string or punctuation — which is what makes them pronouns. `eso` and
# `aquello` are neuter and can never introduce a noun, so they need no guard.
#
# || Marcas de que la pregunta se apoya en el turno anterior. La distinción
# que importa es DETERMINANTE vs PRONOMBRE, y equivocarla se midió en vez de
# suponerse: una versión anterior matcheaba `esa|ese|esos` en cualquier lado y
# disparaba en 3 de las 35 preguntas del golden set —«esos boletines», «esa
# cobranza», «ese pago»—, todas con sujeto propio. Reescribirlas habría
# agregado un referente a una pregunta que ya tenía uno: justo la falla que
# advierte la sección 6 del `design.md`. Por eso los demostrativos con género
# cuentan solo cuando no los sigue nada —fin de cadena o puntuación—, que es
# lo que los vuelve pronombres. `eso` y `aquello` son neutros y nunca pueden
# introducir un sustantivo, así que no necesitan guarda.
_END_OF_CLAUSE = r"(?=\s*(?:[?!.,;:)]|$))"
_REFERENTIAL = re.compile(
    r"(^\s*¿?\s*y\b)"
    r"|\b(eso|aquello)\b"
    rf"|\b(esa|ese|esos|esas)\b{_END_OF_CLAUSE}"
    rf"|\b(la|el) mism[ao]\b{_END_OF_CLAUSE}"
    r"|\blo anterior\b"
    r"|\ball[íi]\b"
    r"|\bah[íi]\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResolvedQuestion:
    """The question to retrieve with, and what was substituted to get it.

    ``substituted`` is empty when nothing was rewritten, which is the common
    case and the one that must stay indistinguishable from having no session
    at all.

    || La pregunta con la que buscar, y qué se sustituyó para obtenerla.
    ``substituted`` vacío significa que no se reescribió nada — el caso común,
    y el que tiene que quedar indistinguible de no tener sesión.
    """

    text: str
    substituted: list[str]

    @property
    def rewritten(self) -> bool:
        """Whether the question changed. || Si la pregunta cambió."""
        return bool(self.substituted)


def resolve(question: str, facts: ConversationFacts | None) -> ResolvedQuestion:
    """Name the referent explicitly when the question only points at it.

    || Nombra el referente explícitamente cuando la pregunta solo lo señala.
    """
    text = (question or "").strip()
    if not text or facts is None:
        return ResolvedQuestion(text=text, substituted=[])

    # It names its own subject. Nothing to resolve, and rewriting it would be
    # the module inventing a second subject.
    # || Nombra su propio sujeto. No hay nada que resolver, y reescribirla
    # sería inventarle un segundo sujeto.
    if _TRANSACTION_TOKEN.search(text):
        return ResolvedQuestion(text=text, substituted=[])

    if not _REFERENTIAL.search(text):
        return ResolvedQuestion(text=text, substituted=[])

    # What the previous answer actually cited is the strongest referent
    # available: it is what the user was reading when they wrote this. The
    # codes merely mentioned along the way are the fallback.
    # || Lo que citó la respuesta anterior es el referente más fuerte: es lo
    # que el usuario estaba leyendo cuando escribió esto. Los códigos apenas
    # mencionados son el respaldo.
    referents = facts.last_document_ids or facts.transaction_codes
    if not referents:
        return ResolvedQuestion(text=text, substituted=[])

    named = referents[:MAX_REFERENTS]
    resolved = f"{text} (sobre {', '.join(named)})"
    log.info(
        "conversation_question_resolved",
        question_chars=len(text),
        referents=named,
    )
    return ResolvedQuestion(text=resolved, substituted=named)

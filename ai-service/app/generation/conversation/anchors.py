"""Detect the scope constraints a user pins on the conversation.

The course anchors durable commitments of ITS domain — a signed NDA, a frozen
scope, a locked budget — because forgetting one would make an estimate wrong.
The structure is worth keeping and the vocabulary is not: nothing in a
functional-spec Q&A is a contractual commitment. What plays the same role
here is a user narrowing the corpus on purpose ("de acá en adelante, solo
módulo CA"), because forgetting it silently widens every later search.

Heuristic only, no LLM. The course offers an LLM classifier as an opt-in
because a paraphrased commitment is hard to catch with regexes. Here the
anchor set is small and the user states it in so many words, so a classifier
would be one call per turn to decide something already explicit.

Conservative on purpose, in the same direction as the course: a miss just
leaves the turn in the ordinary window, while a false positive silently
narrows every following search — the exact failure this is meant to prevent.

|| Detecta las restricciones de alcance que el usuario fija en la conversación.

El curso ancla los compromisos durables de SU dominio (NDA firmado, scope
congelado, budget lockeado). La estructura sirve; el vocabulario no: en un Q&A
sobre especificaciones funcionales nada es un compromiso contractual. Lo que
cumple ese papel acá es que el usuario acote el corpus a propósito, porque
olvidarlo ensancha en silencio cada búsqueda posterior.

Solo heurística, sin LLM: el conjunto de anchors es chico y el usuario lo dice
con todas las letras. Conservador a propósito — un falso negativo deja el turno
en la ventana común, un falso positivo acota en silencio todo lo que sigue.
"""

from __future__ import annotations

import re

import structlog

from app.generation.conversation.models import Anchor

log = structlog.get_logger()

# The phrase has to SCOPE, not merely mention. "en el módulo CA" is a filter
# for one question; "de acá en adelante, módulo CA" is a decision about the
# conversation. Only the second kind is an anchor.
# || La frase tiene que ACOTAR, no solo mencionar. «en el módulo CA» es un
# filtro de una pregunta; «de acá en adelante, módulo CA» es una decisión sobre
# la conversación. Solo la segunda clase es un anchor.
_SCOPING_PHRASE = re.compile(
    r"\b("
    r"de (?:ac[áa]|aqu[íi]|ahora) en (?:adelante|m[áa]s)"
    r"|de ahora en (?:adelante|m[áa]s)"
    r"|para (?:todo|el resto de) (?:lo que sigue|la conversaci[óo]n|las (?:pr[óo]ximas )?preguntas)"
    r"|(?:siempre|solo|s[óo]lo|[úu]nicamente) (?:dentro de |en |del |de )?(?:el )?(?:m[óo]dulo|ventanas? de tipo)"
    r"|limit[áa](?:te)?(?: solo| s[óo]lo)? a"
    r"|qued[áa](?:te)?(?: solo| s[óo]lo)? (?:en|con)"
    r")\b",
    re.IGNORECASE,
)

# "módulo CA" pins a TRANSACTION PREFIX, not a `module_code`. The word means
# two things: for a person the module of `CA014` is «CA», for the corpus its
# `module_code` is `DMECAR` — the `WINDOWS` module node the breadcrumb came
# from. Pinning "CA" as a `module_code` matched nothing and silently emptied
# every later turn of the conversation, which is worse than not pinning at
# all, because the user did ask for it.
# || «módulo CA» fija un PREFIJO DE TRANSACCIÓN, no un `module_code`. La
# palabra significa dos cosas: para una persona el módulo de `CA014` es «CA»
# y para el corpus su `module_code` es `DMECAR`. Fijar «CA» como `module_code`
# no matcheaba nada y vaciaba en silencio todos los turnos siguientes, que es
# peor que no fijar nada porque el usuario sí lo pidió.
_MODULE = re.compile(r"\bm[óo]dulo\s+([A-Za-z]{2,4})\b", re.IGNORECASE)
_WINDOW_TYPE = re.compile(
    r"\bventanas?\s+(?:de\s+)?tipo\s+[\"'«]?([\wáéíóúñ ]{2,40}?)[\"'»]?(?:[.,;]|$)",
    re.IGNORECASE,
)


def detect_anchors(question: str) -> list[Anchor]:
    """The constraints this question pins, if any.

    Both halves are required: a scoping phrase AND something concrete to pin.
    "de acá en adelante sé más breve" scopes nothing the retriever can use and
    correctly yields no anchor.

    || Las restricciones que esta pregunta fija, si hay alguna. Hacen falta
    las dos mitades: una frase que acota Y algo concreto que fijar. «de acá en
    adelante sé más breve» no acota nada que el retriever pueda usar, y
    correctamente no produce ningún anchor.
    """
    if not question or not _SCOPING_PHRASE.search(question):
        return []

    anchors: list[Anchor] = []
    for match in _MODULE.finditer(question):
        anchors.append(
            Anchor(
                kind="transaction_prefix",
                value=match.group(1).upper(),
                source_question=question,
            )
        )
    for match in _WINDOW_TYPE.finditer(question):
        value = match.group(1).strip()
        if value:
            anchors.append(
                Anchor(kind="window_type_name", value=value, source_question=question)
            )

    if anchors:
        log.info(
            "conversation_anchor_detected",
            anchors=[(anchor.kind, anchor.value) for anchor in anchors],
        )
    return anchors

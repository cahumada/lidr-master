"""A compound question split into the questions it actually asks.

Measured on 35 human-authored questions, 85 question-document pairs: 15 of them
had the relevant document nowhere in a 60-wide candidate set, and **all 15 were
compound questions -- zero on simple ones**. Ten of those missing documents are
the annotated answer of some *other*, simple question in the same set: `CA003`
comes back first for "how many digits does the CBU have" and is absent from the
top 60 of the PAC/TRANSBANK question that has it annotated as relevant.

The document is retrievable. The compound query is what buries it.

|| Una pregunta compuesta partida en las preguntas que realmente hace.

Medido sobre 35 preguntas escritas por una persona, 85 pares pregunta-documento:
en 15 el documento relevante no estaba en ninguna parte de un candidato de 60, y
**los 15 son de preguntas compuestas — cero en simples**. Diez de esos
documentos ausentes son la respuesta anotada de OTRA pregunta, simple, del mismo
conjunto: `CA003` sale primero para "cuántos dígitos tiene la CBU" y está
afuera del top-60 de la pregunta de PAC/TRANSBANK que lo tiene anotado como
relevante.

El documento es recuperable. La consulta compuesta es lo que lo entierra.
"""

from __future__ import annotations

import re

# The interrogatives these questions actually use. Written out instead of
# matched loosely because the whole point is the lookahead: a comma only ends a
# clause when what follows starts a new question.
# || Los interrogativos que estas preguntas usan de verdad. Escritos uno por uno
# en lugar de matchear laxo porque todo el punto es el lookahead: una coma
# termina una cláusula solo cuando lo que sigue arranca otra pregunta.
_INTERROGATIVE = (
    r"(?:c[oó]mo|qu[eé]|cu[aá]l(?:es)?|cu[aá]ndo|d[oó]nde|qui[eé]n(?:es)?|"
    r"cu[aá]nt[oa]s?|por\s+qu[eé]|para\s+qu[eé]|de\s+qu[eé]\s+manera|"
    r"en\s+qu[eé]|bajo\s+qu[eé]|con\s+qu[eé]|a\s+qu[eé]|desde\s+qu[eé])"
)

# Shape 1: coordinated clauses, each carrying its own interrogative.
#   [context], ¿cómo aaa, cómo bbb y en qué ccc?
# || Forma 1: cláusulas coordinadas, cada una con su propio interrogativo.
_CLAUSE_BOUNDARY = re.compile(
    rf",\s*(?={_INTERROGATIVE}\b)|\s+[ye]\s+(?={_INTERROGATIVE}\b)", re.IGNORECASE
)

# A determiner in head position is what separates a coordinated noun phrase from
# any old enumeration inside a single phrase. Without that anchor the rule
# splits "pendientes, cheques a fecha" and produces nonsense.
# || Un determinante en cabeza es lo que distingue una frase nominal coordinada
# de cualquier enumeración adentro de una sola frase. Sin ese ancla la regla
# parte "pendientes, cheques a fecha" y produce basura.
_DETERMINER = r"(?:el|la|los|las|su|sus|un|una|unos|unas|cada)"

# Shape 2: coordinated noun phrases sharing the interrogative AND the verb.
#   ¿Cómo puedo consultar [A], [B] y [C]?
# || Forma 2: frases nominales coordinadas que comparten el interrogativo Y el
# verbo.
_NOUN_BOUNDARY = re.compile(
    rf",\s*(?={_DETERMINER}\s)|\s+y\s+(?={_DETERMINER}\s)", re.IGNORECASE
)

_DETERMINER_HEAD = re.compile(rf"\b{_DETERMINER}\s", re.IGNORECASE)

_OPENING = "¿"


def _context_and_body(question: str) -> tuple[str, str]:
    """The part before the ``¿`` and the part after, without the ``?``.

    || La parte antes del ``¿`` y la parte después, sin el ``?``.
    """
    opening = question.find(_OPENING)
    if opening == -1:
        return "", question.rstrip("?").strip()
    context = question[:opening].strip().rstrip(",").strip()
    return context, question[opening + 1 :].rstrip("?").strip()


def _split_clauses(question: str) -> list[str]:
    """Shape 1. The context goes to every sub-question, because that is where
    the entities are: ``PAC``, ``TRANSBANK``, the receipt. The bare clause "de
    qué manera afecta a la generación manual de su boletín de cobro" names none
    of the three.

    || Forma 1. El contexto va a cada subconsulta, porque ahí están las
    entidades: ``PAC``, ``TRANSBANK``, el recibo. La cláusula suelta "de qué
    manera afecta a la generación manual de su boletín de cobro" no menciona
    ninguna de las tres.
    """
    context, body = _context_and_body(question)
    clauses = [part.strip() for part in _CLAUSE_BOUNDARY.split(body) if part and part.strip()]
    if len(clauses) < 2:
        return []
    if context:
        return [f"{context}, {clause}?" for clause in clauses]
    return [f"{clause}?" for clause in clauses]


def _split_noun_phrases(question: str) -> list[str]:
    """Shape 2. There is no interrogative per part: there is one shared head
    (``¿Cómo puedo consultar de forma estructurada``) and three noun phrases.
    The head is cut at the first determiner of the first segment.

    || Forma 2. No hay un interrogativo por parte: hay una cabeza compartida
    (``¿Cómo puedo consultar de forma estructurada``) y tres frases nominales.
    La cabeza se recorta en el primer determinante del primer segmento.
    """
    context, body = _context_and_body(question)
    parts = [part.strip() for part in _NOUN_BOUNDARY.split(body) if part and part.strip()]
    if len(parts) < 2:
        return []

    head_at = _DETERMINER_HEAD.search(parts[0])
    if head_at is None:
        return []
    head = parts[0][: head_at.start()].strip()
    if not head:
        return []

    segments = [parts[0][head_at.start() :].strip(), *parts[1:]]
    prefix = f"{context}, {_OPENING}{head}" if context else f"{_OPENING}{head}"
    return [f"{prefix} {segment}?" for segment in segments]


def decompose(question: str) -> list[str]:
    """The sub-questions, or an empty list when there is nothing to split.

    An empty list is a valid answer and the common one: of the 35 human-authored
    questions 15 come back whole, and 11 of those are single-document. Not
    splitting a simple question is correct -- the first variant of this split
    broke `U-SI501-reasignar`, sending `SI501` from the top 10 to rank 11 and
    `SI501_k` to 16, on a question that was already answered.

    Clauses are tried before noun phrases: a question with coordinated clauses
    also has determiners inside it, so the noun rule would split it wrongly. The
    clause rule is the more specific one.

    || Las subconsultas, o una lista vacía cuando no hay nada que dividir.

    La lista vacía es una respuesta válida y la más común: de las 35 preguntas
    escritas por una persona 15 vuelven enteras, y 11 de esas son de un solo
    documento. No dividir una pregunta simple es lo correcto — la primera
    variante de esta división rompió `U-SI501-reasignar`, y mandó `SI501` del
    top-10 al puesto 11 y `SI501_k` al 16, en una pregunta que ya estaba
    resuelta.

    Se prueban cláusulas antes que frases nominales: una pregunta con cláusulas
    coordinadas también tiene determinantes adentro, así que la regla nominal la
    partiría mal. La de cláusulas es la más específica.
    """
    return _split_clauses(question) or _split_noun_phrases(question)

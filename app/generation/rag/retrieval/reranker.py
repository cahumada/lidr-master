"""Reordenar el candidato para que lo relevante llegue al top-k.

Con la descomposición ya en su lugar, 28 de los 85 pares pregunta-documento del
golden set tienen su documento en el candidato de 60 pero afuera del top-10.
Eso es un problema de RANGO, y es lo único que un reranker puede arreglar:
reordenar no trae lo que no vino.

Medido sobre las 35 preguntas escritas por una persona [VERIFICADO-CORPUS]:

    oráculo (un reranker perfecto)   +28 pares   p@10 0,220
    con modelo (gpt-4o-mini)         +8 a +10    p@10 0,163-0,169
    léxico determinista              +4          p@10 0,151
    sin reordenar                      —         p@10 0,140

**Un reranker NO puede ser libre de regresiones**, y esa es la diferencia
importante con la descomposición. Reordenar dentro de 10 puestos es de suma
cero: promover un documento al top-10 necesariamente baja a otro. Medido, el de
modelo rescata 15-16 pares y rompe 6-7. El neto es lo que lo justifica, no la
ausencia de daño.

|| Reordering the candidate set so the relevant documents reach the top k.

With decomposition in place, 28 of the golden set's 85 question-document pairs
have their document inside the 60-wide candidate but outside the top 10. That is
a RANK problem, and it is the only thing a reranker can fix: reordering does not
bring back what never came.

A reranker CANNOT be regression-free, which is the important difference from
decomposition. Reordering within 10 places is zero-sum: promoting one document
necessarily demotes another. Measured, the model-based one rescues 15-16 pairs
and breaks 6-7. What justifies it is the net, not the absence of harm.
"""

from __future__ import annotations

import json
import re
from typing import Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)

# How many candidates the reranker sees. 60 is where the measurement was taken
# and it is also the width at which "rank problem" and "recall problem" were
# defined, so moving it changes what those words mean.
# || Cuántos candidatos ve el reranker. 60 es donde se midió y también es el
# ancho con el que se definieron "problema de rango" y "problema de recall", así
# que moverlo cambia lo que esas palabras significan.
DEFAULT_RERANK_CANDIDATES = 60

# Chars of each candidate's text put in the prompt. 60 candidates at 300 chars
# is ~5k tokens of input, which is what makes one call per query affordable.
# || Caracteres del texto de cada candidato que van al prompt. 60 candidatos a
# 300 caracteres son ~5k tokens de entrada, que es lo que hace pagable una
# llamada por consulta.
EXCERPT_CHARS = 300


@runtime_checkable
class Reranker(Protocol):
    """Takes the query and the candidates, returns them reordered.

    A ``Protocol`` for the same reason ``Embedder`` is one: the retrieval layer
    never imports OpenAI, and the tests never need a network.

    || Un ``Protocol`` por la misma razón que ``Embedder`` lo es: la capa de
    recuperación nunca importa OpenAI, y los tests nunca necesitan red.
    """

    def rerank(self, query: str, candidates: list) -> list: ...


# --- Determinista, sin red || Deterministic, no network ------------------------

# Words too short or too common to discriminate. Measured: title overlap alone
# separates relevant from irrelevant 66% to 32%, but used ALONE as the score it
# makes things worse (-2 pairs) -- it has to sit on top of the fused rank.
# || Palabras demasiado cortas o comunes para discriminar. Medido: la
# coincidencia de título separa relevante de irrelevante 66% contra 32%, pero
# usada SOLA como puntaje empeora (-2 pares) — tiene que ir encima del rango
# fusionado.
_STOPWORDS = frozenset(
    {
        "como", "cual", "cuales", "para", "desde", "sobre", "entre", "cuando",
        "donde", "sistema", "puedo", "debo", "tiene", "estan", "hacer",
        "realizar", "manera", "esta", "este", "estos", "estas", "todos",
        "todas", "porque", "segun",
    }
)
_ACCENTS = str.maketrans("áéíóúñ", "aeioun")
_WORD = re.compile(r"[a-z_0-9]{5,}")


def content_words(text: str) -> set[str]:
    """Content words, unaccented, at least 5 chars, minus the stopwords.

    || Palabras de contenido, sin acentos, de 5 caracteres o más, sin las
    palabras vacías.
    """
    plain = text.lower().translate(_ACCENTS)
    return {word for word in _WORD.findall(plain) if word not in _STOPWORDS}


def overlap(query_words: set[str], text: str) -> float:
    """The share of the query's content words present in ``text``.

    || La proporción de palabras de contenido de la consulta que están en
    ``text``.
    """
    if not query_words:
        return 0.0
    return len(query_words & content_words(text)) / len(query_words)


class LexicalReranker:
    """Title plus text overlap, added on top of the fused rank.

    Worth +4 pairs of the 28. Kept because it needs no network and no key, so
    it is what the tests and any offline run use -- and because a measured 4 is
    a better default than an unmeasured 0 when the model is unavailable.

    || Vale +4 pares de los 28. Se queda porque no necesita red ni clave, así
    que es lo que usan los tests y cualquier corrida sin conexión — y porque un
    4 medido es un default mejor que un 0 sin medir cuando el modelo no está.
    """

    def rerank(self, query: str, candidates: list) -> list:
        query_words = content_words(query)
        original = {id(chunk): position for position, chunk in enumerate(candidates)}

        def score(chunk) -> float:
            # The original position enters as a prior: this reorders a list that
            # is already ordered, it does not start from nothing.
            # || El puesto original entra como prior: esto reordena una lista que
            # ya está ordenada, no empieza de cero.
            prior = 1.0 / (DEFAULT_RERANK_CANDIDATES + original[id(chunk)] + 1)
            return (
                overlap(query_words, chunk.document_title or "")
                + overlap(query_words, chunk.text)
                + 0.5 * overlap(query_words, chunk.section or "")
                + prior
            )

        return sorted(candidates, key=score, reverse=True)


# --- Con modelo || Model-based -------------------------------------------------

# The `_k` sentence is not prompt decoration and not annotation leakage: it says
# what a suffix MEANS, never which document answers what. It was added because
# the three documents the reranker pushed OUT of the top 10 were `DP003_k`,
# `CA001k` and `CA001k` -- all header transactions. The model skipped them
# because "Solicitud de clave para..." reads like a form, when in this
# architecture it is the entry point and carries the full functional
# description: `CA001k` has 338 chunks, `CA001A` ("Tratamiento de pólizas") has
# 4. Adding it cut the breakage from 10-11 pairs to 5-7.
# || La frase del `_k` no es adorno del prompt ni filtración de anotaciones:
# dice qué SIGNIFICA un sufijo, nunca qué documento responde qué. Se agregó
# porque los tres documentos que el reranker EMPUJÓ AFUERA del top-10 eran
# `DP003_k`, `CA001k` y `CA001k` — todas transacciones de encabezado. El modelo
# no las elegía porque "Solicitud de clave para..." parece un formulario, cuando
# en esta arquitectura es el punto de acceso y lleva la descripción funcional
# completa. Agregarla bajó las roturas de 10-11 pares a 5-7.
SYSTEM_PROMPT = (
    "Sos un reordenador de resultados de busqueda sobre especificaciones "
    "funcionales de un sistema de seguros, en espanol. Recibis una pregunta y "
    "una lista de documentos candidatos. Devolves los que responden la "
    "pregunta, el mejor primero.\n"
    "Una pregunta compuesta necesita VARIOS documentos: incluilos todos.\n"
    "Contexto de la arquitectura: un codigo que termina en `_k` o `k` es la "
    "TRANSACCION DE ENCABEZADO, el punto de acceso a esa funcionalidad. Su "
    "titulo dice 'Solicitud de clave para...' y parece un formulario, pero "
    "suele llevar la descripcion funcional completa del proceso. Para una "
    "pregunta sobre COMO se hace algo, la transaccion de encabezado casi "
    "siempre es parte de la respuesta.\n"
    "Respondes SOLO un objeto JSON: {\"ids\": [\"ID1\", \"ID2\", ...]}, "
    "EXACTAMENTE 10 ids si hay 10 candidatos plausibles, tomados de la lista "
    "recibida y ordenados del mejor al peor."
)


def render_candidates(query: str, candidates: list) -> str:
    """One line per candidate: id, title, section, excerpt.

    || Una línea por candidato: id, título, sección, extracto.
    """
    lines = [f"PREGUNTA: {query}", "", "CANDIDATOS:"]
    for chunk in candidates:
        excerpt = " ".join(chunk.text.split())[:EXCERPT_CHARS]
        lines.append(
            f"- {chunk.document_id} | {chunk.document_title or '(sin titulo)'}"
            f" | {chunk.section or '-'} | {excerpt}"
        )
    return "\n".join(lines)


class LLMReranker:
    """Asks a model which candidates answer the question.

    Worth +8 to +10 pairs of the 28, against +4 for the lexical one. Measured
    over three identical runs the spread is 57-59 pairs in the top 10, so the
    gain is reported as a range: ``temperature=0`` is not determinism.

    The model choice is NOT the bottleneck: ``gpt-4o`` scored exactly the same
    +11 as ``gpt-4o-mini`` on the run they were compared, at 5.6 s against
    3.3 s. The cheaper one is the default for that reason.

    || Vale +8 a +10 pares de los 28, contra +4 del léxico. Medido sobre tres
    corridas idénticas el rango es 57-59 pares en el top-10, así que la ganancia
    se reporta como rango: ``temperature=0`` no es determinismo.

    La elección de modelo NO es el cuello de botella: ``gpt-4o`` sacó exactamente
    el mismo +11 que ``gpt-4o-mini`` en la corrida donde se compararon, a 5,6 s
    contra 3,3 s. El más barato es el default por eso.
    """

    def __init__(self, client, *, model: str) -> None:
        self._client = client
        self.model = model

    def rerank(self, query: str, candidates: list) -> list:
        if not candidates:
            return []

        by_document = {chunk.document_id: chunk for chunk in candidates}
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": render_candidates(query, candidates)},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            chosen = json.loads(response.choices[0].message.content).get("ids", [])
        except Exception as error:  # noqa: BLE001
            # A reranker that fails must not take the query with it: the fused
            # order is a real answer, just a worse-ordered one.
            # || Un reranker que falla no se puede llevar la consulta puesta: el
            # orden fusionado es una respuesta real, solo peor ordenada.
            logger.warning("rerank_failed", error=str(error), model=self.model)
            return candidates

        # An id that was not in the list is a hallucination. Dropped and
        # counted: measured at 1 in 35 queries with `gpt-4o-mini` and 0 with
        # `gpt-4o`, which is low but not zero, and silently trusting it would
        # mean returning a document the search never found.
        # || Un id que no estaba en la lista es una alucinación. Se descarta y se
        # cuenta: medido en 1 de 35 consultas con `gpt-4o-mini` y 0 con
        # `gpt-4o`, que es poco pero no cero, y confiarle en silencio sería
        # devolver un documento que la búsqueda nunca encontró.
        promoted, invented = [], 0
        seen: set[str] = set()
        for raw in chosen:
            document_id = str(raw)
            if document_id in by_document and document_id not in seen:
                promoted.append(by_document[document_id])
                seen.add(document_id)
            elif document_id not in by_document:
                invented += 1
        if invented:
            logger.warning("rerank_invented_ids", count=invented, model=self.model)

        rest = [chunk for chunk in candidates if chunk.document_id not in seen]
        return promoted + rest

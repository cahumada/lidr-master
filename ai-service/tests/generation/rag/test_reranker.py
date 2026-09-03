"""El reranker: el léxico determinista y el de modelo con un cliente falso.

Ninguno de estos tests toca la red. El de modelo se prueba contra un doble que
devuelve exactamente lo que se le dice, incluido lo que devuelve mal.
"""

from dataclasses import dataclass

import pytest

from app.generation.rag.retrieval.reranker import (
    DEFAULT_RERANK_CANDIDATES,
    LexicalReranker,
    LLMReranker,
    Reranker,
    content_words,
    overlap,
    render_candidates,
)


@dataclass
class FakeChunk:
    """Lo mínimo que un reranker mira de un chunk."""

    document_id: str
    document_title: str | None = None
    section: str | None = None
    text: str = ""


def chunks(*ids: str) -> list[FakeChunk]:
    return [FakeChunk(document_id=i, text=f"texto de {i}") for i in ids]


# --- Palabras de contenido -----------------------------------------------------


def test_short_words_are_not_content():
    """Menos de 5 caracteres no discrimina en este corpus."""
    assert content_words("la caja de un mes") == set()


def test_accents_do_not_split_a_word():
    """El corpus está en español y los documentos no siempre acentúan igual."""
    assert content_words("póliza") == content_words("poliza")


def test_stopwords_are_dropped():
    assert "sistema" not in content_words("que hace el sistema")
    assert "cobranzas" in content_words("que hace el sistema de cobranzas")


def test_overlap_of_nothing_is_zero():
    """Una consulta sin palabras de contenido no puede puntuar."""
    assert overlap(set(), "cualquier texto") == 0.0


def test_overlap_is_the_share_of_the_query_found():
    query = content_words("domiciliacion bancaria")
    assert overlap(query, "la domiciliacion se registra") == pytest.approx(0.5)


# --- El léxico determinista ----------------------------------------------------


def test_the_lexical_reranker_promotes_a_title_match():
    candidates = [
        FakeChunk("OTRO", document_title="Otra cosa", text="nada que ver"),
        FakeChunk("CO634", document_title="Informacion del traspaso de pago", text="x"),
    ]

    ordered = LexicalReranker().rerank("como se hace el traspaso de pago", candidates)

    assert ordered[0].document_id == "CO634"


def test_the_lexical_reranker_keeps_the_original_order_as_a_prior():
    """Sin señal léxica no se reordena nada: el puesto original entra al puntaje,
    así que empatados en 0 quedan como estaban. Reordena una lista que ya está
    ordenada, no empieza de cero."""
    candidates = chunks("A", "B", "C")

    ordered = LexicalReranker().rerank("consulta sin ninguna coincidencia", candidates)

    assert [c.document_id for c in ordered] == ["A", "B", "C"]


def test_the_lexical_reranker_returns_every_candidate():
    """Un reranker reordena, no filtra. Quedarse con menos sería perder
    candidatos que el recorte a `limit` todavía no descartó."""
    candidates = chunks(*[f"D{i}" for i in range(20)])
    assert len(LexicalReranker().rerank("cualquier cosa", candidates)) == 20


# --- El de modelo, con un cliente falso ----------------------------------------


class FakeClient:
    """Devuelve el JSON que se le pasa, o levanta lo que se le pasa."""

    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self._content = content
        self._error = error
        self.calls = 0
        self.chat = self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls += 1
        if self._error is not None:
            raise self._error

        @dataclass
        class Message:
            content: str

        @dataclass
        class Choice:
            message: Message

        @dataclass
        class Response:
            choices: list

        return Response(choices=[Choice(message=Message(content=self._content))])


def test_the_model_ranking_is_applied():
    client = FakeClient('{"ids": ["C", "A"]}')

    ordered = LLMReranker(client, model="m").rerank("q", chunks("A", "B", "C"))

    assert [c.document_id for c in ordered] == ["C", "A", "B"]


def test_an_invented_id_is_dropped():
    """Un id que no estaba en la lista es una alucinación. Medido en 1 de 35
    consultas: poco pero no cero, y confiarle en silencio sería devolver un
    documento que la búsqueda nunca encontró."""
    client = FakeClient('{"ids": ["NO_EXISTE", "B"]}')

    ordered = LLMReranker(client, model="m").rerank("q", chunks("A", "B"))

    assert [c.document_id for c in ordered] == ["B", "A"]


def test_a_repeated_id_is_not_duplicated():
    client = FakeClient('{"ids": ["A", "A", "B"]}')

    ordered = LLMReranker(client, model="m").rerank("q", chunks("A", "B"))

    assert [c.document_id for c in ordered] == ["A", "B"]


def test_every_candidate_survives_the_reranking():
    """Lo que el modelo no elige va detrás, nunca se descarta: el recorte a
    `limit` es del llamador, y un candidato perdido acá no vuelve."""
    client = FakeClient('{"ids": ["C"]}')

    ordered = LLMReranker(client, model="m").rerank("q", chunks("A", "B", "C", "D"))

    assert {c.document_id for c in ordered} == {"A", "B", "C", "D"}
    assert ordered[0].document_id == "C"


def test_a_failing_model_returns_the_candidates_untouched():
    """Un reranker que falla no se puede llevar la consulta puesta: el orden
    fusionado es una respuesta real, solo peor ordenada."""
    client = FakeClient(error=RuntimeError("503"))

    ordered = LLMReranker(client, model="m").rerank("q", chunks("A", "B"))

    assert [c.document_id for c in ordered] == ["A", "B"]


def test_malformed_json_does_not_raise():
    client = FakeClient("no soy json")
    assert len(LLMReranker(client, model="m").rerank("q", chunks("A", "B"))) == 2


def test_no_candidates_means_no_call():
    """Reordenar nada no necesita un modelo."""
    client = FakeClient('{"ids": []}')

    assert LLMReranker(client, model="m").rerank("q", []) == []
    assert client.calls == 0


# --- El prompt -----------------------------------------------------------------


def test_the_prompt_carries_every_candidate_id():
    """Si un id no está en el prompt, el modelo no lo puede elegir."""
    rendered = render_candidates("q", chunks("A", "B", "C"))
    for document_id in ("A", "B", "C"):
        assert document_id in rendered


def test_the_prompt_carries_the_question():
    assert "como se traspasa un pago" in render_candidates("como se traspasa un pago", chunks("A"))


# --- El contrato ---------------------------------------------------------------


def test_both_implementations_satisfy_the_protocol():
    assert isinstance(LexicalReranker(), Reranker)
    assert isinstance(LLMReranker(FakeClient('{"ids": []}'), model="m"), Reranker)


def test_the_candidate_width_is_wider_than_a_normal_k():
    """Reordenar los mismos 10 que la búsqueda ya eligió no tiene con qué
    trabajar: los 28 pares convertibles están entre el puesto 11 y el 60."""
    assert DEFAULT_RERANK_CANDIDATES >= 60

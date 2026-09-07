"""The two chat adapters against doubles. No network, no API key.

|| Los dos adaptadores de chat contra dobles. Sin red, sin clave.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.foundation.llm.wrapper import (
    LLM,
    UNREPORTED_USAGE,
    AnthropicChatLLM,
    LLMError,
    OpenAICompatibleChatLLM,
)

# --- OpenAI-compatible (OpenAI y Moonshot/Kimi) -------------------------------


class FakeCompletions:
    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeOpenAIClient:
    def __init__(self, script: list) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(script))


def _openai_usage(*, prompt: int = 100, completion: int = 40, total: int = 140):
    return SimpleNamespace(
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=total
    )


def _completion(
    text: str | None,
    *,
    empty_choices: bool = False,
    finish_reason: str = "stop",
    usage=None,
):
    if empty_choices:
        return SimpleNamespace(choices=[], usage=usage)
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text), finish_reason=finish_reason
            )
        ],
        usage=usage,
    )


def _openai_llm(
    script: list, *, temperature: float | None = 0.0
) -> tuple[OpenAICompatibleChatLLM, FakeOpenAIClient]:
    client = FakeOpenAIClient(script)
    return (
        OpenAICompatibleChatLLM(
            client, model="gpt-4o-mini", max_tokens=256, temperature=temperature
        ),
        client,
    )


class TestOpenAICompatibleChatLLM:
    def test_complete_returns_the_assistant_text(self):
        llm, _ = _openai_llm(
            [_completion("El capital no puede superar el máximo. [CA014 · Validaciones]")]
        )

        completion = llm.complete(system="sé breve", user="¿cuál es el tope?")

        assert "CA014" in completion.text
        assert completion.truncated is False

    def test_complete_sends_system_and_user_and_the_configured_knobs(self):
        llm, client = _openai_llm([_completion("ok")])

        llm.complete(system="system-text", user="user-text")

        call = client.chat.completions.calls[0]
        assert call["model"] == "gpt-4o-mini"
        assert call["max_tokens"] == 256
        assert call["temperature"] == 0.0
        assert call["messages"] == [
            {"role": "system", "content": "system-text"},
            {"role": "user", "content": "user-text"},
        ]

    def test_a_null_temperature_is_not_sent_at_all(self):
        # Not "sent as null": the parameter has to be absent, because a
        # provider that rejects it rejects the key, not the value.
        # || No "mandada como null": el parámetro tiene que estar ausente,
        # porque un proveedor que la rechaza rechaza la clave, no el valor.
        llm, client = _openai_llm([_completion("ok")], temperature=None)

        llm.complete(system="s", user="u")

        assert "temperature" not in client.chat.completions.calls[0]

    def test_empty_content_is_an_error(self):
        llm, _ = _openai_llm([_completion("")])

        with pytest.raises(LLMError, match="empty content"):
            llm.complete(system="s", user="u")

    def test_no_choices_is_an_error(self):
        llm, _ = _openai_llm([_completion(None, empty_choices=True)])

        with pytest.raises(LLMError, match="no choices"):
            llm.complete(system="s", user="u")

    def test_the_wrapper_satisfies_the_protocol(self):
        llm, _ = _openai_llm([_completion("ok")])
        assert isinstance(llm, LLM)


# --- Anthropic Messages -------------------------------------------------------


class FakeMessages:
    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeAnthropicClient:
    def __init__(self, script: list) -> None:
        self.messages = FakeMessages(script)


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _anthropic_usage(*, incoming: int = 80, outgoing: int = 20):
    return SimpleNamespace(input_tokens=incoming, output_tokens=outgoing)


def _message(
    blocks: list, *, stop_reason: str = "end_turn", stop_details=None, usage=None
):
    return SimpleNamespace(
        content=blocks, stop_reason=stop_reason, stop_details=stop_details, usage=usage
    )


def _anthropic_llm(
    script: list, *, temperature: float | None = None, model: str = "claude-sonnet-5"
) -> tuple[AnthropicChatLLM, FakeAnthropicClient]:
    client = FakeAnthropicClient(script)
    return (
        AnthropicChatLLM(client, model=model, max_tokens=1024, temperature=temperature),
        client,
    )


class TestAnthropicChatLLM:
    def test_system_goes_as_a_parameter_not_as_a_message(self):
        # The whole reason this adapter exists: Anthropic takes `system` as a
        # request parameter, and a system-role message is not the same thing.
        # || La razón de ser de este adaptador: Anthropic toma `system` como
        # parámetro, y un mensaje con rol system no es lo mismo.
        llm, client = _anthropic_llm([_message([_text_block("ok")])])

        llm.complete(system="system-text", user="user-text")

        call = client.messages.calls[0]
        assert call["system"] == "system-text"
        assert call["messages"] == [{"role": "user", "content": "user-text"}]
        assert call["max_tokens"] == 1024

    def test_the_answer_is_the_text_blocks_joined(self):
        llm, _ = _anthropic_llm(
            [_message([_text_block("primera parte. "), _text_block("segunda parte.")])]
        )

        assert llm.complete(system="s", user="u").text == "primera parte. segunda parte."

    def test_non_text_blocks_are_skipped(self):
        thinking = SimpleNamespace(type="thinking", thinking="...")
        llm, _ = _anthropic_llm([_message([thinking, _text_block("la respuesta")])])

        assert llm.complete(system="s", user="u").text == "la respuesta"

    def test_temperature_is_omitted_when_none(self):
        llm, client = _anthropic_llm([_message([_text_block("ok")])], temperature=None)

        llm.complete(system="s", user="u")

        assert "temperature" not in client.messages.calls[0]

    def test_temperature_is_sent_when_the_caller_supplies_one(self):
        llm, client = _anthropic_llm(
            [_message([_text_block("ok")])], temperature=0.5, model="claude-haiku-4-5"
        )

        llm.complete(system="s", user="u")

        assert client.messages.calls[0]["temperature"] == 0.5

    def test_a_refusal_raises_instead_of_returning_an_empty_answer(self):
        # A policy decline arrives as a successful HTTP 200 with no text.
        # Returning "" would read as "the model had nothing to say".
        # || Un rechazo por política llega como un 200 sin texto. Devolver ""
        # se leería como "el modelo no tenía nada que decir".
        refused = _message(
            [], stop_reason="refusal", stop_details=SimpleNamespace(category="cyber")
        )
        llm, _ = _anthropic_llm([refused])

        with pytest.raises(LLMError, match="declined"):
            llm.complete(system="s", user="u")

    def test_no_text_blocks_is_an_error_that_names_the_stop_reason(self):
        llm, _ = _anthropic_llm([_message([], stop_reason="max_tokens")])

        with pytest.raises(LLMError, match="max_tokens"):
            llm.complete(system="s", user="u")

    def test_the_adapter_satisfies_the_protocol(self):
        llm, _ = _anthropic_llm([_message([_text_block("ok")])])
        assert isinstance(llm, LLM)


class TestTruncationIsReported:
    """A completion cut at the output cap must not look like a whole answer.

    The provider says why it stopped and neither adapter read it, so half an
    answer reached the console marked `grounded` with nothing to suggest it
    was incomplete. These pin both directions on both wire formats.

    || Una completion cortada en el tope no puede parecer una respuesta
    entera. El proveedor dice por qué paró y ningún adaptador lo leía, así
    que media respuesta llegaba a la consola marcada `grounded` sin nada que
    sugiriera que estaba incompleta.
    """

    def test_openai_length_marks_truncated(self):
        llm, _ = _openai_llm([_completion("media resp", finish_reason="length")])

        completion = llm.complete(system="s", user="u")

        assert completion.truncated is True

    def test_openai_stop_does_not(self):
        llm, _ = _openai_llm([_completion("entera", finish_reason="stop")])

        assert llm.complete(system="s", user="u").truncated is False

    def test_anthropic_max_tokens_marks_truncated(self):
        llm, _ = _anthropic_llm(
            [_message([_text_block("media resp")], stop_reason="max_tokens")]
        )

        assert llm.complete(system="s", user="u").truncated is True

    def test_anthropic_end_turn_does_not(self):
        llm, _ = _anthropic_llm(
            [_message([_text_block("entera")], stop_reason="end_turn")]
        )

        assert llm.complete(system="s", user="u").truncated is False

    def test_the_partial_text_comes_back_anyway(self):
        """Mark, do not reject -- same call the citation guardrail made.

        || Marcar y no rechazar, el mismo criterio del guardrail de citas.
        """
        llm, _ = _openai_llm(
            [_completion("lo que alcanzó a escribir", finish_reason="length")]
        )

        completion = llm.complete(system="s", user="u")

        assert completion.text == "lo que alcanzó a escribir"

    def test_a_refusal_is_still_an_error_and_not_a_truncation(self):
        llm, _ = _anthropic_llm(
            [
                _message(
                    [], stop_reason="refusal", stop_details=SimpleNamespace(category="cyber")
                )
            ]
        )

        with pytest.raises(LLMError):
            llm.complete(system="s", user="u")


class TestUsageIsCopiedFromTheProvider:
    """Both wires report tokens; missing usage is marked, not guessed.

    || Los dos wires reportan tokens; un usage ausente se marca, no se adivina.
    """

    def test_openai_usage_is_copied_onto_completion(self):
        llm, _ = _openai_llm(
            [_completion("ok", usage=_openai_usage(prompt=100, completion=40, total=140))]
        )

        usage = llm.complete(system="s", user="u").usage

        assert usage.input_tokens == 100
        assert usage.output_tokens == 40
        assert usage.total_tokens == 140
        assert usage.reported is True

    def test_anthropic_usage_is_normalized_to_the_same_shape(self):
        llm, _ = _anthropic_llm(
            [_message([_text_block("ok")], usage=_anthropic_usage(incoming=80, outgoing=20))]
        )

        usage = llm.complete(system="s", user="u").usage

        assert usage.input_tokens == 80
        assert usage.output_tokens == 20
        assert usage.total_tokens == 100
        assert usage.reported is True

    def test_missing_openai_usage_is_unreported_zeros(self):
        llm, _ = _openai_llm([_completion("el texto")])

        completion = llm.complete(system="s", user="u")

        assert completion.text == "el texto"
        assert completion.usage == UNREPORTED_USAGE

    def test_missing_anthropic_usage_is_unreported_zeros(self):
        llm, _ = _anthropic_llm([_message([_text_block("el texto")])])

        completion = llm.complete(system="s", user="u")

        assert completion.text == "el texto"
        assert completion.usage.reported is False
        assert completion.usage.input_tokens == 0
        assert completion.usage.output_tokens == 0
        assert completion.usage.total_tokens == 0

    def test_partial_openai_usage_is_unreported(self):
        llm, _ = _openai_llm(
            [
                _completion(
                    "ok",
                    usage=SimpleNamespace(
                        prompt_tokens=10, completion_tokens=None, total_tokens=10
                    ),
                )
            ]
        )

        assert llm.complete(system="s", user="u").usage.reported is False

    def test_truncation_still_reports_usage(self):
        llm, _ = _openai_llm(
            [
                _completion(
                    "media resp",
                    finish_reason="length",
                    usage=_openai_usage(prompt=50, completion=256, total=306),
                )
            ]
        )

        completion = llm.complete(system="s", user="u")

        assert completion.truncated is True
        assert completion.usage.total_tokens == 306
        assert completion.usage.reported is True

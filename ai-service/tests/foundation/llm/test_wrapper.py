"""OpenAIChatLLM against a double. No network, no API key.

|| OpenAIChatLLM contra un doble. Sin red, sin clave.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.foundation.llm.wrapper import LLM, LLMError, OpenAIChatLLM


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


class FakeClient:
    def __init__(self, script: list) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(script))


def _completion(text: str | None, *, empty_choices: bool = False):
    if empty_choices:
        return SimpleNamespace(choices=[])
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _llm(script: list) -> tuple[OpenAIChatLLM, FakeClient]:
    client = FakeClient(script)
    return (
        OpenAIChatLLM(client, model="gpt-4o-mini", max_tokens=256, temperature=0.0),
        client,
    )


def test_complete_returns_the_assistant_text():
    llm, _ = _llm([_completion("El capital no puede superar el máximo. [CA014 · Validaciones]")])

    text = llm.complete(system="sé breve", user="¿cuál es el tope?")

    assert "CA014" in text


def test_complete_sends_system_and_user_and_the_configured_knobs():
    llm, client = _llm([_completion("ok")])

    llm.complete(system="system-text", user="user-text")

    call = client.chat.completions.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["max_tokens"] == 256
    assert call["temperature"] == 0.0
    assert call["messages"] == [
        {"role": "system", "content": "system-text"},
        {"role": "user", "content": "user-text"},
    ]


def test_empty_content_is_an_error():
    llm, _ = _llm([_completion("")])

    with pytest.raises(LLMError, match="empty content"):
        llm.complete(system="s", user="u")


def test_no_choices_is_an_error():
    llm, _ = _llm([_completion(None, empty_choices=True)])

    with pytest.raises(LLMError, match="no choices"):
        llm.complete(system="s", user="u")


def test_the_wrapper_satisfies_the_protocol():
    llm, _ = _llm([_completion("ok")])
    assert isinstance(llm, LLM)


def test_get_answer_llm_requires_a_key(monkeypatch):
    """Without a key there is no generation, same as the embedder."""
    from app.config import Settings
    from app.dependencies import get_answer_llm

    get_answer_llm.cache_clear()
    monkeypatch.setattr(
        "app.dependencies.get_settings",
        lambda: Settings(OPENAI_API_KEY=""),
    )

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_answer_llm()

    get_answer_llm.cache_clear()

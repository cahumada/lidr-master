"""Thin adapters over a chat-completions client, one per wire format.

Two adapters cover three providers, and that is not an accident: Moonshot
(Kimi) serves an **OpenAI-compatible** API, so it reuses the OpenAI adapter
with a different ``base_url`` and key. Anthropic's Messages API is a genuinely
different shape — ``system`` is a top-level parameter rather than a message,
``max_tokens`` is required, the response is a list of content blocks, and a
policy decline arrives as HTTP 200 with ``stop_reason == "refusal"`` — so it
gets its own adapter.

Neither adapter builds its own client: the clients are built in
``app/foundation/llm/providers.py`` and nowhere else, the same rule
``get_embedder()`` follows. A ``Protocol`` keeps the generation layer
swappable for a test double, so the tests never need the network.

Still thin on purpose. Retries are the SDKs' job (both retry 429 and 5xx with
backoff by default); token accounting and streaming would each need a real
consumer before they earned a layer here.

|| Adaptadores delgados sobre un cliente de chat, uno por formato de wire.

Dos adaptadores cubren tres proveedores, y no es casualidad: Moonshot (Kimi)
sirve una API **compatible con OpenAI**, así que reusa el adaptador de OpenAI
con otro ``base_url`` y otra clave. La Messages API de Anthropic es una forma
distinta de verdad —``system`` es un parámetro de primer nivel y no un
mensaje, ``max_tokens`` es obligatorio, la respuesta es una lista de bloques,
y un rechazo por política llega como HTTP 200 con ``stop_reason ==
"refusal"``— así que tiene su propio adaptador.

Ningún adaptador arma su cliente: los clientes se arman en
``app/foundation/llm/providers.py`` y en ningún otro lado.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)


class LLMError(RuntimeError):
    """The completion could not be produced. || No se pudo producir la completion."""


@runtime_checkable
class LLM(Protocol):
    """Turns a system + user pair into a completion.

    || Convierte un par system + user en una completion.
    """

    model: str

    def complete(self, *, system: str, user: str) -> str:
        """Return the assistant text for this turn.

        || Devuelve el texto del asistente para este turno.
        """
        ...


class OpenAICompatibleChatLLM:
    """One chat-completions call, no extras. OpenAI and Moonshot (Kimi).

    || Una llamada de chat completions, sin extras. OpenAI y Moonshot (Kimi).
    """

    def __init__(
        self,
        client: Any,
        *,
        model: str,
        max_tokens: int,
        temperature: float | None,
    ) -> None:
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def complete(self, *, system: str, user: str) -> str:
        """Call the chat API and return the assistant message.

        An empty ``content`` is a contract violation from the provider, not a
        valid answer: returning it would look like "the model had nothing to
        say" when what happened is the call produced no text.

        || Llama a la API de chat y devuelve el mensaje del asistente. Un
        ``content`` vacío es una violación de contrato del proveedor, no una
        respuesta válida: devolverlo parecería "el modelo no tenía nada que
        decir" cuando lo que pasó es que la llamada no produjo texto.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        response = self._client.chat.completions.create(**payload)
        if not response.choices:
            raise LLMError("completion returned no choices")
        content = response.choices[0].message.content
        if not content:
            raise LLMError("completion returned empty content")
        logger.info(
            "llm_complete",
            provider="openai_compatible",
            model=self.model,
            system_chars=len(system),
            user_chars=len(user),
            answer_chars=len(content),
        )
        return content


class AnthropicChatLLM:
    """One Messages API call, no extras.

    Three differences from the OpenAI shape that this adapter absorbs so the
    rest of the service never has to know about them:

    * ``system`` is a request parameter, not a message with a role.
    * ``max_tokens`` is required, not optional.
    * The response is a list of content blocks; the answer is the text ones.

    And one that it refuses to hide: a policy decline comes back as a
    successful HTTP 200 with ``stop_reason == "refusal"`` and no text.
    Returning that as an empty answer would read as "the model had nothing to
    say", so it raises instead.

    || Una llamada a la Messages API, sin extras. Tres diferencias con la
    forma de OpenAI que este adaptador absorbe, y una que se niega a esconder:
    un rechazo por política vuelve como un HTTP 200 con ``stop_reason ==
    "refusal"`` y sin texto, así que lanza en vez de devolver vacío.
    """

    def __init__(
        self,
        client: Any,
        *,
        model: str,
        max_tokens: int,
        temperature: float | None,
    ) -> None:
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        # `None` means "do not send it". Current Claude models REJECT sampling
        # parameters with a 400 -- see `providers.py`, which is what decides.
        # || `None` significa "no mandarlo". Los modelos Claude actuales
        # RECHAZAN los parámetros de sampling con un 400 -- lo decide
        # `providers.py`.
        self.temperature = temperature

    def complete(self, *, system: str, user: str) -> str:
        """Call the Messages API and return the assistant text.

        || Llama a la Messages API y devuelve el texto del asistente.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        response = self._client.messages.create(**payload)

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None)
            raise LLMError(f"the model declined this request (category={category!r})")

        text = "".join(
            block.text
            for block in (getattr(response, "content", None) or [])
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        )
        if not text:
            raise LLMError(f"completion returned no text blocks (stop_reason={stop_reason!r})")

        logger.info(
            "llm_complete",
            provider="anthropic",
            model=self.model,
            system_chars=len(system),
            user_chars=len(user),
            answer_chars=len(text),
            stop_reason=stop_reason,
        )
        return text

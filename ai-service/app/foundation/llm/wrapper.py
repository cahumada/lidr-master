"""Thin wrapper over a chat-completions client.

The OpenAI client is built in ``get_answer_llm()`` and nowhere else, the same
rule as ``get_embedder()``. This module never imports OpenAI: a ``Protocol``
keeps the generation layer swappable for a test double, and the tests never
need the network.

Thin on purpose. Retries, token accounting and a second provider would each
need a second consumer before they earned a layer of their own.

|| Wrapper delgado sobre un cliente de chat completions. El cliente de OpenAI
se arma en ``get_answer_llm()`` y en ningún otro lado, la misma regla que
``get_embedder()``. Este módulo nunca importa OpenAI: un ``Protocol`` mantiene
la capa de generación intercambiable por un doble de tests, y los tests nunca
necesitan red.

Delgado a propósito. Reintentos, conteo de tokens y un segundo proveedor
necesitarían cada uno un segundo consumidor antes de merecer una capa propia.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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


class OpenAIChatLLM:
    """One chat-completions call, no extras.

    || Una llamada de chat completions, sin extras.
    """

    def __init__(
        self,
        client,
        *,
        model: str,
        max_tokens: int,
        temperature: float,
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
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        if not response.choices:
            raise LLMError("completion returned no choices")
        content = response.choices[0].message.content
        if not content:
            raise LLMError("completion returned empty content")
        logger.info(
            "llm_complete",
            model=self.model,
            system_chars=len(system),
            user_chars=len(user),
            answer_chars=len(content),
        )
        return content

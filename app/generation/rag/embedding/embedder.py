"""Embedders: the only place that talks to an embedding model.

``Embedder`` is a ``Protocol`` so the batch layer never imports OpenAI. That is
what lets the test suite verify batching, resumption, index mapping and
verification -- where the real bugs are -- without the network or an API key.

|| Embedders: el único lugar que le habla a un modelo de embeddings.

``Embedder`` es un ``Protocol`` para que la capa de batch nunca importe OpenAI.
Eso es lo que permite que la suite verifique batching, reanudación, mapeo de
índices y verificación —donde están los bugs reales— sin red y sin clave.
"""

from __future__ import annotations

import hashlib
import math
import time
from typing import Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)


class EmbeddingError(RuntimeError):
    """A batch could not be embedded. || Un lote no se pudo embeber."""


class DimensionMismatchError(EmbeddingError):
    """The model returned a dimension other than the configured one.

    Not retryable and not survivable: writing a sidecar with mixed dimensions
    would corrupt every consumer of it.

    || El modelo devolvió una dimensión distinta a la configurada. No es
    reintentable ni tolerable: escribir un sidecar con dimensiones mezcladas
    corrompería a todos sus consumidores.
    """


@runtime_checkable
class Embedder(Protocol):
    """Turns texts into vectors. || Convierte textos en vectores."""

    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text, in the same order.

        || Devuelve un vector por texto, en el mismo orden.
        """
        ...


# --- Deterministic embedder for tests || Embedder determinístico para tests --


class HashEmbedder:
    """Derives a vector from the SHA-256 of the text.

    || Deriva el vector del SHA-256 del texto.

    Same text, same vector, no network, no key. It is NOT semantically
    meaningful and must never be used for a real corpus -- it exists so the
    machinery around the embedder can be tested on every run.

    || Mismo texto, mismo vector, sin red y sin clave. NO tiene sentido
    semántico y nunca debe usarse para un corpus real — existe para que la
    maquinaria alrededor del embedder se pueda testear en cada corrida.
    """

    def __init__(self, dimensions: int = 1536) -> None:
        self.model = "hash-embedder"
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        # Stretch the 32-byte digest to `dimensions` floats by re-hashing with
        # a counter, then L2-normalize so the vectors behave like real ones
        # under cosine similarity.
        # || Estira el digest de 32 bytes a `dimensions` floats re-hasheando con
        # un contador, y normaliza L2 para que los vectores se comporten como
        # los reales bajo similitud coseno.
        raw = bytearray()
        counter = 0
        seed = text.encode("utf-8")
        while len(raw) < self.dimensions:
            raw.extend(hashlib.sha256(seed + counter.to_bytes(4, "big")).digest())
            counter += 1
        values = [(byte / 127.5) - 1.0 for byte in raw[: self.dimensions]]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


# --- OpenAI || OpenAI --------------------------------------------------------

# Transient: worth waiting for. Anything else (400 invalid input, 401 bad key)
# is not retried -- retrying only delays the diagnosis.
# || Transitorios: vale la pena esperar. Cualquier otro (400 input inválido,
# 401 clave mala) no se reintenta — reintentar solo demora el diagnóstico.
RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})


def is_retryable(error: Exception) -> bool:
    """Whether ``error`` is worth another attempt.

    || Si vale la pena reintentar ``error``.
    """
    status = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status in RETRYABLE_STATUS_CODES
    # No status at all: a connection reset or a timeout, which is transient.
    # || Sin status: un reset de conexión o un timeout, que es transitorio.
    return isinstance(error, (ConnectionError, TimeoutError))


class OpenAIEmbedder:
    """``text-embedding-3-small`` with retries and exponential backoff.

    || ``text-embedding-3-small`` con reintentos y backoff exponencial.
    """

    def __init__(
        self,
        client,
        *,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        max_retries: int = 5,
        retry_base_delay: float = 1.0,
        sleep=time.sleep,
    ) -> None:
        self._client = client
        self.model = model
        self.dimensions = dimensions
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._sleep = sleep

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed one batch, retrying transient failures.

        || Embebe un lote, reintentando los fallos transitorios.
        """
        if not texts:
            return []

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._call(texts)
            except DimensionMismatchError:
                # A wrong dimension is a contract violation, not bad luck.
                # || Una dimensión equivocada es una violación de contrato, no mala suerte.
                raise
            except Exception as error:  # noqa: BLE001 -- re-raised below as EmbeddingError
                last_error = error
                if not is_retryable(error) or attempt == self._max_retries:
                    break
                delay = self._retry_base_delay * (2**attempt)
                logger.warning(
                    "embedding_batch_retry",
                    attempt=attempt + 1,
                    of=self._max_retries,
                    delay_seconds=delay,
                    error=str(error),
                )
                self._sleep(delay)

        raise EmbeddingError(f"batch of {len(texts)} failed: {last_error}") from last_error

    def _call(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self.model, input=texts)
        # The API documents that `data` comes back in input order, but the
        # index field is authoritative -- sorting by it costs nothing and
        # removes the assumption.
        # || La API documenta que `data` vuelve en el orden de entrada, pero el
        # campo index es autoritativo — ordenar por él no cuesta nada y elimina
        # el supuesto.
        items = sorted(response.data, key=lambda item: item.index)
        if len(items) != len(texts):
            raise EmbeddingError(f"asked for {len(texts)} vectors, got {len(items)}")

        vectors = [list(item.embedding) for item in items]
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise DimensionMismatchError(
                    f"model returned {len(vector)} dims, expected {self.dimensions}"
                )
        return vectors

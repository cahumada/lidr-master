"""Shared helpers for chunking strategies.

The course's ``chunking/base.py`` (session_16) also defines an abstract
``Chunker`` class + a strategy-comparison log event, because that project
runs several interchangeable chunking strategies side by side. This project
has exactly one strategy (:mod:`app.generation.rag.chunking.functional_spec`),
so only the genuinely shared piece — token counting against the embedding
model's tokenizer — is replicated here; the strategy-comparison scaffolding
would be an abstraction with a single implementation.

|| Helpers compartidos para las estrategias de chunking.

El ``chunking/base.py`` del curso (session_16) también define una clase
abstracta ``Chunker`` + un evento de log para comparar estrategias, porque
ese proyecto corre varias estrategias de chunking intercambiables en
paralelo. Este proyecto tiene exactamente una estrategia
(:mod:`app.generation.rag.chunking.functional_spec`), así que acá solo se
replica la pieza genuinamente compartida — contar tokens contra el
tokenizer del modelo de embeddings —; el andamiaje de comparación de
estrategias sería una abstracción con una sola implementación.
"""

from __future__ import annotations

import tiktoken

# text-embedding-3-small's tokenizer, per the embedding_pipeline convention.
# || Tokenizer de text-embedding-3-small, siguiendo la convención de embedding_pipeline.
_ENCODING = tiktoken.encoding_for_model("text-embedding-3-small")


def count_tokens(text: str) -> int:
    """Token count of ``text`` using the embedding model's tokenizer.

    || Cantidad de tokens de ``text`` usando el tokenizer del modelo de embeddings.
    """
    return len(_ENCODING.encode(text))

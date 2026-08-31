"""FastAPI dependency factories for shared singletons.

Mirrors ``app/dependencies.py`` on the ``session_16`` branch of
LIDR-academy/ai-engineering — the composition root that wires singletons,
kept separate from the routers (which stay transport-only) and from the
chunker itself (which stays framework-agnostic).

|| Factories de dependencias de FastAPI para singletons compartidos.
Replica ``app/dependencies.py`` en la rama ``session_16`` de
LIDR-academy/ai-engineering — el composition root que arma los singletons,
separado de los routers (que se quedan solo como transporte) y del chunker
en sí (que se queda agnóstico del framework).
"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.generation.rag.chunking.functional_spec import FunctionalSpecChunker
from app.generation.rag.embedding.embedder import OpenAIEmbedder
from app.generation.rag.navigation import get_navigation_tree


@lru_cache
def get_functional_spec_chunker() -> FunctionalSpecChunker:
    """Chunker singleton, configured from Settings.

    || Singleton del chunker, configurado desde Settings.
    """
    settings = get_settings()
    return FunctionalSpecChunker(
        narrative_token_cap=settings.NARRATIVE_CHUNK_TOKEN_CAP,
        index_doc_min_links=settings.INDEX_DOC_MIN_LINKS,
        index_doc_min_link_density=settings.INDEX_DOC_MIN_LINK_DENSITY,
        navigation_tree=get_navigation_tree(settings.WINDOWS_TREE_PATH),
        tenant_id=settings.TENANT_ID,
        doc_version=settings.DOC_VERSION,
    )


@lru_cache
def get_embedder() -> OpenAIEmbedder:
    """Embedder singleton, configured from Settings.

    The OpenAI client is built HERE and nowhere else, so no other module has to
    know about the provider — that is what keeps ``Embedder`` swappable for the
    deterministic test double.

    || Singleton del embedder, configurado desde Settings. El cliente de OpenAI
    se arma ACÁ y en ningún otro lado, así ningún otro módulo tiene que conocer
    al proveedor — es lo que mantiene a ``Embedder`` intercambiable por el doble
    determinístico de tests.
    """
    from openai import OpenAI

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in. "
            "|| OPENAI_API_KEY no está definida. Copiá .env.example a .env y completala."
        )

    return OpenAIEmbedder(
        OpenAI(api_key=settings.OPENAI_API_KEY),
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
        max_retries=settings.EMBEDDING_MAX_RETRIES,
        retry_base_delay=settings.EMBEDDING_RETRY_BASE_DELAY,
    )

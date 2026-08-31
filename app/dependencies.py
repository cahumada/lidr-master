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

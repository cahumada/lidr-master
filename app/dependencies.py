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


def get_hybrid_retriever(session):
    """Retriever for one session. || Retriever para una sesión.

    Not cached: it holds the session, whose lifetime is the request's. The
    embedder inside it IS cached, so the OpenAI client is built once.

    || Sin cachear: sostiene la sesión, cuya vida es la del request. El embedder
    que tiene adentro SÍ está cacheado, así que el cliente de OpenAI se arma una
    sola vez.
    """
    from app.generation.rag.retrieval.hybrid import HybridRetriever
    from app.generation.rag.store.repository import ChunkRepository

    return HybridRetriever(ChunkRepository(session), get_embedder())


@lru_cache
def get_reranker():
    """Reranker singleton. The model-based one when there is a key, the lexical
    one when there is not.

    Falling back instead of raising is deliberate and measured: the lexical
    reranker is worth +4 pairs of the 28 convertible ones, and a measured 4 beats
    an unmeasured 0. An embedder has no such fallback -- without vectors there is
    no search at all -- so `get_embedder` still raises.

    || Singleton del reranker. El de modelo cuando hay clave, el léxico cuando
    no. Caer al léxico en lugar de fallar es deliberado y medido: vale +4 pares
    de los 28 convertibles, y un 4 medido le gana a un 0 sin medir. Un embedder
    no tiene ese respaldo —sin vectores no hay búsqueda— así que `get_embedder`
    sigue fallando.
    """
    from app.generation.rag.retrieval.reranker import LexicalReranker, LLMReranker

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return LexicalReranker()

    from openai import OpenAI

    return LLMReranker(OpenAI(api_key=settings.OPENAI_API_KEY), model=settings.RERANK_MODEL)


@lru_cache
def get_corpus_source():
    """Corpus source singleton: the bucket when one is configured, the local
    directory otherwise.

    `CORPUS_BUCKET` is what decides, and not a flag: a bucket name and a
    directory path are mutually exclusive by nature, and a separate switch would
    be one more thing that can disagree with them.

    || Singleton de la fuente del corpus: el bucket cuando hay uno configurado,
    el directorio local si no. `CORPUS_BUCKET` es lo que decide, y no un flag:
    un nombre de bucket y una ruta son excluyentes por naturaleza, y un
    interruptor aparte sería una cosa más que puede contradecirlos.
    """
    from app.ingestion.source import LocalCorpusSource, S3CorpusSource

    settings = get_settings()
    if settings.CORPUS_BUCKET:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
            region_name=settings.S3_REGION or None,
        )
        return S3CorpusSource(
            client, bucket=settings.CORPUS_BUCKET, prefix=settings.CORPUS_BUCKET_PREFIX
        )

    if settings.CORPUS_ROOT is None:
        raise RuntimeError(
            "Neither CORPUS_BUCKET nor CORPUS_ROOT is configured, so there is no corpus "
            "to read. || No hay CORPUS_BUCKET ni CORPUS_ROOT configurados, así que no hay "
            "corpus que leer."
        )
    return LocalCorpusSource(settings.CORPUS_ROOT)

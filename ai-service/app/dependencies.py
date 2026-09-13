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

import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.business_db_store import resolve_active_run, resolve_active_run_sync
from app.foundation.persistence.database import get_async_session
from app.generation.rag.business_db.models import BusinessDbContext
from app.generation.rag.business_db.render import render_block
from app.generation.rag.business_db.resolve import anchored_codes, resolve_context
from app.generation.rag.chunking.functional_spec import FunctionalSpecChunker
from app.generation.rag.embedding.embedder import OpenAIEmbedder
from app.generation.rag.navigation import (
    NavigationTree,
    get_navigation_tree,
    get_navigation_tree_for_run,
)
from app.generation.rag.schemas import SearchHit


def resolve_navigation_tree(env: str | None = None, run_id: str | None = None):
    """The WINDOWS tree for one run: the mirror when there is one, the CSV otherwise.

    Takes the run as ARGUMENTS rather than reading it from settings, which is
    the whole point: the run is now a selection that can change while the
    process lives, and a function that resolves it from the environment would
    pin every caller to whatever was configured at boot.

    Called with no arguments it falls back to the CSV, where status stays
    unresolved because the export has no `SSTATREGT` column.

    || El árbol WINDOWS de UNA corrida: el mirror cuando hay, el CSV si no. La
    corrida entra por ARGUMENTOS y no se lee de settings, que es el punto: ahora
    es una selección que puede cambiar mientras el proceso vive, y una función
    que la resolviera del ambiente pegaría a cada llamador a lo que estaba
    configurado al arrancar.
    """
    settings = get_settings()
    if run_id:
        return get_navigation_tree_for_run(
            settings.DATABASE_URL,
            settings.TENANT_ID,
            env or settings.BUSINESS_DB_ENV,
            run_id,
        )
    return get_navigation_tree(settings.WINDOWS_TREE_PATH)


def resolve_business_db_context(
    env: str | None,
    run_id: str | None,
    codes: list[str],
) -> BusinessDbContext:
    """What the active run declares for ``codes``. Sync, cached by table.

    Same shape as :func:`resolve_navigation_tree`: the run arrives as
    arguments, the tree and the reader are process caches keyed by that run.
    Both answer paths call THIS function, so they cannot disagree about what
    the base says.

    Without a run there is no block and no fallback to the latest run or the
    CSV — the dictionary and the rows only live in the mirror.

    || Lo que declara la corrida activa para ``codes``. Sincrónico, cacheado
    por tabla. Los dos caminos de respuesta usan ESTA función. Sin corrida
    no hay bloque ni caída a la más reciente ni al CSV.
    """
    settings = get_settings()
    if not run_id:
        return BusinessDbContext.absent(
            "no_active_run",
            env=env,
            detail=(
                "No hay corrida activa; el diccionario y las filas solo viven "
                "en el mirror. || No active run; the dictionary and the rows "
                "only live in the mirror."
            ),
        )
    resolved_env = env or settings.BUSINESS_DB_ENV
    tree = resolve_navigation_tree(resolved_env, run_id)
    return resolve_context(
        database_url=settings.DATABASE_URL,
        tenant=settings.TENANT_ID,
        env=resolved_env,
        run_id=run_id,
        codes=codes,
        tree=tree,
        max_rows=settings.BUSINESS_DB_CONTEXT_MAX_ROWS,
        as_of_override=settings.BUSINESS_DB_CONTEXT_AS_OF or None,
        with_tables=settings.BUSINESS_DB_DEPENDENCY_TABLES_ENABLED,
        max_tables=settings.BUSINESS_DB_DEPENDENCY_MAX_TABLES,
    )


def business_db_for_run(env: str | None, run_id: str | None):
    """A `business_db_for` callable bound to one run, for `build_budgeted_messages`.

    Receives the hits that entered the prompt and the tokens still unused.
    Both answer paths use this so they cannot pick different codes or a
    different ceiling.

    || Un callable `business_db_for` atado a una corrida. Los dos caminos de
    respuesta usan este, para que no elijan códigos ni techo distintos.
    """
    settings = get_settings()

    def _for(kept: list[SearchHit], remaining: int) -> BusinessDbContext:
        if not settings.BUSINESS_DB_CONTEXT_ENABLED:
            return BusinessDbContext.absent("disabled", env=env)
        codes, dropped = anchored_codes(
            kept, max_codes=settings.BUSINESS_DB_CONTEXT_MAX_CODES
        )
        context = resolve_business_db_context(env, run_id, codes)
        context = context.model_copy(update={"dropped_codes": list(dropped)}).with_completeness()
        allowance = min(settings.BUSINESS_DB_CONTEXT_MAX_TOKENS, max(remaining, 0))
        return render_block(context, budget=allowance)

    return _for


# Keyed by the run, and bounded. `@lru_cache` with NO arguments — which is what
# this was — pinned the chunker to whichever run happened to be resolved when
# the process booted, and the resulting bug is one of the worst available: two
# replicas of the service serving different navigation trees depending on when
# each one started. The tree is inside the chunker, so the chunker's identity is
# the run's identity.
# || Con la corrida en la clave, y acotado. Un `@lru_cache` SIN argumentos —que
# es lo que era— pegaba el chunker a la corrida que se hubiera resuelto al
# arrancar el proceso, y el bug resultante es de los peores: dos réplicas del
# servicio sirviendo árboles distintos según cuándo arrancó cada una. El árbol
# vive adentro del chunker, así que la identidad del chunker es la de la corrida.
@lru_cache(maxsize=4)
def build_functional_spec_chunker(
    env: str | None = None, run_id: str | None = None
) -> FunctionalSpecChunker:
    """The chunker for one run. || El chunker de una corrida."""
    settings = get_settings()
    return FunctionalSpecChunker(
        narrative_token_cap=settings.NARRATIVE_CHUNK_TOKEN_CAP,
        index_doc_min_links=settings.INDEX_DOC_MIN_LINKS,
        index_doc_min_link_density=settings.INDEX_DOC_MIN_LINK_DENSITY,
        navigation_tree=resolve_navigation_tree(env, run_id),
        tenant_id=settings.TENANT_ID,
        doc_version=settings.DOC_VERSION,
    )


async def get_functional_spec_chunker(
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's required DI idiom.
) -> FunctionalSpecChunker:
    """Chunker for the run that is active right now.

    Async because resolving the active run is a query: the selection lives in a
    table, so a request served after an activation gets the new tree without a
    redeploy and without a restart.

    || Chunker de la corrida activa ahora. Async porque resolver la corrida es
    una consulta: la selección vive en una tabla, así que un request servido
    después de una activación recibe el árbol nuevo sin redeploy ni reinicio.
    """
    active = await resolve_active_run(session, get_settings())
    return build_functional_spec_chunker(active.env, active.run_id)


def get_functional_spec_chunker_sync() -> FunctionalSpecChunker:
    """Same chunker, for the batch paths that cannot await.

    The rebuild runs in a thread and the scripts are plain ``main()``s. They
    still resolve the SELECTED run: a batch that chunks against a run nobody
    chose would stamp the corpus with it.

    || El mismo chunker, para los caminos batch que no pueden await. Igual
    resuelven la corrida SELECCIONADA: un batch que trocea contra una corrida
    que nadie eligió estamparía el corpus con ella.
    """
    settings = get_settings()
    active = resolve_active_run_sync(settings.DATABASE_URL, settings)
    return build_functional_spec_chunker(active.env, active.run_id)


def resolve_active_navigation_tree_sync() -> NavigationTree | None:
    """The tree of the active run, for sync callers. || El árbol de la corrida activa."""
    settings = get_settings()
    active = resolve_active_run_sync(settings.DATABASE_URL, settings)
    return resolve_navigation_tree(active.env, active.run_id)


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
def get_answer_llm():
    """Generation LLM from the SETTINGS ONLY — no database.

    This is the offline path: `scripts/eval_generation.py` measures the same
    generation function the endpoint calls, and it must not need Postgres or a
    provider row to do it. Credentials come from the environment and the
    provider from ``ANSWER_PROVIDER``, resolved against the built-in seed
    registry.

    The endpoints do NOT use this: they go through
    ``app.domain.profiles.synthesizer_runtime``, which reads the provider and
    its credential from the database so a change in the console applies
    without a restart.

    || LLM de generación desde los SETTINGS SOLAMENTE, sin base. Es el camino
    offline: el script de eval mide la misma función que llama el endpoint y no
    puede necesitar Postgres para hacerlo. Los endpoints NO usan esto: pasan
    por ``synthesizer_runtime``, que lee proveedor y credencial de la base.
    """
    from app.domain.providers_store import ResolvedProvider
    from app.foundation.llm.providers import build_llm_for, seed_provider

    settings = get_settings()
    spec = seed_provider(settings.ANSWER_PROVIDER)
    if spec is None:
        raise RuntimeError(
            f"ANSWER_PROVIDER={settings.ANSWER_PROVIDER!r} is not a built-in provider; the "
            "settings-only path cannot resolve one added from the console. "
            "|| ANSWER_PROVIDER no es un proveedor incorporado; el camino "
            "solo-settings no puede resolver uno agregado desde la consola."
        )

    base_url = spec.base_url
    if spec.id == "moonshot":
        base_url = settings.MOONSHOT_BASE_URL or base_url

    resolved = ResolvedProvider(
        id=spec.id,
        label=spec.label,
        wire=spec.wire,
        base_url=base_url,
        enabled=True,
        note=spec.note,
        api_key_setting=spec.api_key_setting,
        api_key=str(getattr(settings, spec.api_key_setting, "") or ""),
        api_key_hint=None,
        key_source="env",
    )
    return build_llm_for(
        resolved,
        settings.ANSWER_MODEL,
        max_tokens=settings.ANSWER_MAX_TOKENS,
        temperature=settings.ANSWER_TEMPERATURE,
        supports_temperature=True,
    )


@lru_cache
def get_activity_log():
    """Activity log singleton for live agentic-run visibility.

    A singleton and not per-request: the log has to outlive the request that
    started the background run, since a later, unrelated request is the one
    that polls it.

    || Singleton del log de actividad para visibilidad en vivo de corridas
    agenticas. Singleton y no por-request: el log tiene que sobrevivir al
    request que arrancó la corrida en background, porque quien lo consulta es
    otro request posterior y sin relación.
    """
    from app.domain.graph.activity import GraphActivityLog

    return GraphActivityLog()


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
        return S3CorpusSource(client, bucket=settings.CORPUS_BUCKET)

    if settings.CORPUS_ROOT is None:
        raise RuntimeError(
            "Neither CORPUS_BUCKET nor CORPUS_ROOT is configured, so there is no corpus "
            "to read. || No hay CORPUS_BUCKET ni CORPUS_ROOT configurados, así que no hay "
            "corpus que leer."
        )
    return LocalCorpusSource(settings.CORPUS_ROOT)


def require_service_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Reject a caller that does not carry the service's shared secret.

    Applied at ROUTER level in ``app/main.py`` and not endpoint by endpoint, so
    an endpoint added tomorrow is closed without anyone remembering to close
    it. ``/health`` is the one exception, and it is registered outside the
    protected routers.

    With no ``SERVICE_TOKEN`` configured this passes: the environment is
    declared open (see ``Settings.SERVICE_TOKEN``), which is what lets the
    tests and the evals run. Production without a token does not boot, so this
    branch cannot be the production posture by accident.

    The comparison is ``compare_digest`` and not ``==``: an equality that
    short-circuits leaks the shared prefix through timing. And the 401 does not
    say whether the header was missing or wrong — that difference only helps
    somebody trying tokens.

    || Rechaza a quien no trae el secreto compartido del servicio. Se aplica a
    nivel de ROUTER en ``app/main.py`` y no endpoint por endpoint, así un
    endpoint agregado mañana queda cerrado sin que nadie se acuerde de
    cerrarlo. ``/health`` es la única excepción y se registra afuera.

    Sin ``SERVICE_TOKEN`` configurado esto pasa: el entorno está declarado
    abierto, que es lo que permite correr los tests y los evals. Producción sin
    token no arranca, así que esta rama no puede ser la postura de producción
    por descuido.

    La comparación es ``compare_digest`` y no ``==``: una igualdad que corta al
    primer byte distinto filtra el prefijo por tiempo. Y el 401 no dice si el
    header faltaba o estaba mal — esa diferencia solo le sirve a quien está
    probando tokens.
    """
    expected = get_settings().SERVICE_TOKEN.strip()
    if not expected:
        return

    presented = ""
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[len("bearer ") :].strip()

    if not secrets.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service token required. || Se requiere el token del servicio.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# The header the console's BFF uses to say who is asking.
# || El header con el que el BFF de la consola dice quién pregunta.
CONSOLE_USER_HEADER = "X-Console-User"

# An id longer than this is not a console user id; it is somebody probing.
# || Un id más largo que esto no es un id de usuario de la consola.
_MAX_OWNER_ID_CHARS = 64


def resolve_console_user(
    x_console_user: Annotated[str | None, Header()] = None,
) -> str | None:
    """Who the BFF says is asking, or ``None`` when nobody said.

    Trustworthy for the same reason the service token is: ``add-service-
    authentication`` left the BFF as the only holder of ``SERVICE_TOKEN``, and
    this header travels inside that same request. It adds no surface — whoever
    can send it can already send the token.

    ``None`` is NOT "anyone": it is its own bucket of ownerless conversations,
    enforced by ``SessionStore``. Making absence mean "no filter" would turn the
    protection off by dropping a header.

    An over-long value is refused rather than truncated: truncating would make
    two different ids collide into one owner, which is the failure this exists
    to prevent.

    || Quién dice el BFF que pregunta, o ``None`` si nadie lo dijo. Es confiable
    por la misma razón que el token: el BFF es su único portador y este header
    viaja adentro del mismo request. ``None`` NO es «cualquiera»: es su propio
    balde de conversaciones sin dueño. Un valor demasiado largo se rechaza y no
    se trunca — truncar haría colisionar dos ids distintos en un mismo dueño,
    que es justamente la falla que esto viene a evitar.
    """
    if x_console_user is None:
        return None
    owner_id = x_console_user.strip()
    if not owner_id:
        return None
    if len(owner_id) > _MAX_OWNER_ID_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{CONSOLE_USER_HEADER} is longer than {_MAX_OWNER_ID_CHARS} characters. "
                f"|| {CONSOLE_USER_HEADER} supera los {_MAX_OWNER_ID_CHARS} caracteres."
            ),
        )
    return owner_id

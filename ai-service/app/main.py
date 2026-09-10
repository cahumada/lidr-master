"""FastAPI application entrypoint. || Punto de entrada de la aplicación FastAPI.

Composition root: wires the config, configures logging, and includes the
routers. Mirrors ``app/main.py`` on the ``session_16`` branch of
LIDR-academy/ai-engineering, scaled down to what this project actually has.

|| Composition root: arma la config, configura el logging, e incluye los
routers. Replica ``app/main.py`` en la rama ``session_16`` de
LIDR-academy/ai-engineering, reducido a lo que este proyecto realmente tiene.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import AsyncExitStack, asynccontextmanager

import structlog
from fastapi import Depends, FastAPI

from app.api.answer import router as answer_router
from app.api.answer_agentic import router as answer_agentic_router
from app.api.answer_session import list_router as answer_sessions_router
from app.api.answer_session import router as answer_session_router
from app.api.business_db import router as business_db_router
from app.api.config import router as config_router
from app.api.corpus import router as corpus_router
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.usage import router as usage_router
from app.config import get_settings
from app.dependencies import require_service_token


def configure_logging() -> None:
    """Set up structlog: JSON in production, human-readable in development.

    || Configura structlog: JSON en producción, legible por humanos en desarrollo.
    """
    settings = get_settings()

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.APP_ENV == "production"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle.

    || Ciclo de vida de arranque y apagado de la aplicación.
    """
    configure_logging()
    settings = get_settings()

    # The one signal that an environment is answering anyone. `Settings` already
    # refuses to boot in production without the token, so reaching this branch
    # there is impossible — but a staging URL that someone shared is exactly the
    # case this line exists to make findable in a log.
    # || La única señal de que un entorno le está contestando a cualquiera.
    # `Settings` ya se niega a arrancar en producción sin el token, así que
    # llegar acá allá es imposible — pero una URL de staging que alguien
    # compartió es justo el caso que esta línea existe para hacer buscable.
    if not settings.SERVICE_TOKEN.strip():
        log.warning(
            "service_auth_disabled",
            app_env=settings.APP_ENV,
            detail="SERVICE_TOKEN is empty: every endpoint answers without credentials",
        )

    async def _seed_providers() -> None:
        try:
            from app.domain.providers_store import seed_if_empty
            from app.foundation.persistence.database import get_async_session_factory

            async with get_async_session_factory()() as session:
                await seed_if_empty(session, settings)
        except Exception as exc:  # noqa: BLE001 — seeding is best-effort.
            log.error("providers_seed_failed", error=str(exc)[:400])

    # Providers and their models live in the database so adding one is a row
    # and not a deploy. Seeding is idempotent and additive, so a fresh install
    # behaves as it did when the catalog was an env var, and a restart never
    # undoes an edit made from the console.
    #
    # Failing to seed does NOT stop the service: the tables may be
    # unreachable, and a service that answers nothing because it could not
    # write a catalog row is worse than one that reports the provider as
    # unavailable. Seeding touches a remote DB and can take seconds, so it runs
    # in the background and must not block `/health`, `/docs` or `/config`.
    # || Los proveedores y sus modelos viven en la base, así que agregar uno es
    # una fila y no un deploy. El seeding es idempotente y aditivo. Si falla NO
    # detiene el servicio. Toca una base remota y puede tardar segundos, así que
    # corre en background y no debe bloquear `/health`, `/docs` ni `/config`.
    seed_task = asyncio.create_task(_seed_providers())

    app.state.answer_graph = None
    app.state._graph_stack = AsyncExitStack()

    checkpointer = None
    try:
        from app.domain.graph.checkpointer import open_checkpointer

        checkpointer = await app.state._graph_stack.enter_async_context(open_checkpointer())
    except Exception as exc:  # noqa: BLE001 — graph is optional infrastructure.
        log.error("answer_graph_checkpointer_init_failed", error=str(exc)[:400])

    if checkpointer is not None:
        try:
            from app.domain.graph.build import build_answer_graph

            app.state.answer_graph = build_answer_graph(checkpointer)
            log.info("answer_graph_ready")
        except Exception as exc:  # noqa: BLE001
            log.error("answer_graph_init_failed", error=str(exc)[:400])

    log.info("application_started", environment=settings.APP_ENV)
    yield
    with contextlib.suppress(Exception):
        await seed_task
    await app.state._graph_stack.aclose()
    log.info("application_shutdown")


app = FastAPI(title="Visual Time RAG — servicio IA", version="0.1.0", lifespan=lifespan)
# Every router carries the token dependency; `/health` is declared outside them
# and stays open because it is the platform's healthcheck. Putting the guard
# HERE and not on each endpoint is deliberate: an endpoint added tomorrow is
# closed without anyone remembering to close it, and the list of what is open
# is one line long instead of scattered across nine files.
# || Todos los routers llevan la dependencia del token; `/health` se declara
# afuera y queda abierto porque es el healthcheck de la plataforma. Poner la
# guarda ACÁ y no en cada endpoint es deliberado: un endpoint agregado mañana
# queda cerrado sin que nadie se acuerde, y la lista de lo que está abierto
# mide una línea en vez de estar repartida en nueve archivos.
_PROTECTED = [Depends(require_service_token)]

for _router in (
    documents_router,
    search_router,
    answer_router,
    answer_agentic_router,
    answer_sessions_router,
    answer_session_router,
    config_router,
    corpus_router,
    usage_router,
    business_db_router,
):
    app.include_router(_router, dependencies=_PROTECTED)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

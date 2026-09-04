"""FastAPI application entrypoint. || Punto de entrada de la aplicación FastAPI.

Composition root: wires the config, configures logging, and includes the
routers. Mirrors ``app/main.py`` on the ``session_16`` branch of
LIDR-academy/ai-engineering, scaled down to what this project actually has.

|| Composition root: arma la config, configura el logging, e incluye los
routers. Replica ``app/main.py`` en la rama ``session_16`` de
LIDR-academy/ai-engineering, reducido a lo que este proyecto realmente tiene.
"""

from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.answer import router as answer_router
from app.api.answer_agentic import router as answer_agentic_router
from app.api.config import router as config_router
from app.api.corpus import router as corpus_router
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.config import get_settings


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
    await app.state._graph_stack.aclose()
    log.info("application_shutdown")


app = FastAPI(title="Visual Time RAG — servicio IA", version="0.1.0", lifespan=lifespan)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(answer_router)
app.include_router(answer_agentic_router)
app.include_router(config_router)
app.include_router(corpus_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

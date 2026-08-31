"""FastAPI application entrypoint. || Punto de entrada de la aplicación FastAPI.

Composition root: wires the config, configures logging, and includes the
routers. Mirrors ``app/main.py`` on the ``session_16`` branch of
LIDR-academy/ai-engineering, scaled down to what this project actually has
(no lifespan-managed DB/graph checkpointer — nothing here needs one yet).

|| Composition root: arma la config, configura el logging, e incluye los
routers. Replica ``app/main.py`` en la rama ``session_16`` de
LIDR-academy/ai-engineering, reducido a lo que este proyecto realmente
tiene (sin checkpointer de DB/grafo manejado por lifespan — todavía nada
acá lo necesita).
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from app.api.documents import router as documents_router
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


configure_logging()

app = FastAPI(title="Visual Time RAG — servicio IA", version="0.1.0")
app.include_router(documents_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

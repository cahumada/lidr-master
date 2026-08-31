"""Application settings, loaded from environment variables and .env.

Mirrors ``app/config.py`` on the ``session_16`` branch of
LIDR-academy/ai-engineering (``pydantic-settings`` + a cached singleton
accessor). Only the knobs this project actually uses are declared — no
placeholder LLM/embedding-provider settings for layers that don't exist yet.

|| Configuración de la aplicación, cargada desde variables de entorno y
.env. Replica ``app/config.py`` en la rama ``session_16`` de
LIDR-academy/ai-engineering (``pydantic-settings`` + un accessor singleton
cacheado). Solo se declaran los knobs que este proyecto realmente usa — sin
settings de relleno para capas de LLM/embeddings que todavía no existen.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"

    # Token budget for a narrative chunk (Función/Efecto/Notas), tiktoken
    # cl100k_base via text-embedding-3-small's encoding.
    # || Presupuesto de tokens para un chunk narrativo (Función/Efecto/Notas),
    # tiktoken cl100k_base vía el encoding de text-embedding-3-small.
    NARRATIVE_CHUNK_TOKEN_CAP: int = 500

    # Index/chapter document detection. A document with no pure-table section
    # and a high density of links to other documents is a navigation node, not
    # content. Both thresholds are CALIBRATED against the corpus, not derived,
    # so they are settings rather than constants: the captured set was reviewed
    # by hand at these values (see the change's design note).
    # || Detección de documento índice/capítulo. Un documento sin sección de
    # tabla pura y con alta densidad de enlaces a otros documentos es un nodo de
    # navegación, no contenido. Ambos umbrales están CALIBRADOS contra el corpus,
    # no derivados, así que son settings y no constantes: el conjunto capturado
    # se revisó a mano con estos valores (ver la nota de diseño del cambio).
    INDEX_DOC_MIN_LINKS: int = 5
    INDEX_DOC_MIN_LINK_DENSITY: float = 3.0

    # CSV export of the WINDOWS table (code, parent_code, description).
    # OPTIONAL: a missing file simply leaves every breadcrumb unresolved.
    # || Export CSV de la tabla WINDOWS (code, parent_code, description).
    # OPCIONAL: si el archivo falta, todos los breadcrumb quedan sin resolver.
    WINDOWS_TREE_PATH: Path = Path("data/windows_tree.csv")

    # Version identity of the corpus being chunked. Stamped onto every
    # chunk so a vector store can isolate one client and one documentation
    # version; also declared in the corpus manifest. Overridable per run
    # (--tenant / --doc-version), because one deployment serves several
    # clients on possibly different documentation versions.
    # || Identidad de versión del corpus que se trocea. Se estampa en cada
    # chunk para que un vector store pueda aislar un cliente y una versión
    # de la documentación; también se declara en el manifiesto del corpus.
    # Sobreescribible por corrida (--tenant / --doc-version), porque un
    # despliegue sirve a varios clientes en versiones posiblemente distintas.
    TENANT_ID: str = "life_seguros"
    DOC_VERSION: str = "DW Funtionals 2026.1"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (singleton).

    || Devuelve la configuración de la aplicación cacheada (singleton).
    """
    return Settings()

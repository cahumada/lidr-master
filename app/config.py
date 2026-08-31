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
    # Generic defaults on purpose: the real client id and documentation
    # version are deployment data and live in the local .env, not in a
    # public repository.
    # || Defaults genéricos a propósito: el id del cliente real y la versión
    # de la documentación son datos del despliegue y viven en el .env local,
    # no en un repositorio público.
    TENANT_ID: str = "default_tenant"
    DOC_VERSION: str = "unversioned"

    # --- Embedding layer || Capa de embeddings -----------------------------

    # The API key lives in the local .env, never in the repository. Absent, the
    # deterministic test embedder still works; only the real run needs it.
    # || La clave de API vive en el .env local, nunca en el repositorio. Si
    # falta, el embedder determinístico de tests igual funciona; solo la
    # corrida real la necesita.
    OPENAI_API_KEY: str = ""

    # 1536 dims, NOT truncated via MRL: 380 MB is not a storage problem here,
    # and shrinking the dimension is a quality loss that only pays off when the
    # index does not fit. The value is verified against what the API actually
    # returns rather than assumed.
    # || 1536 dims, SIN recortar vía MRL: 380 MB no es un problema de
    # almacenamiento acá, y recortar la dimensión es una pérdida de calidad que
    # solo se justifica cuando el índice no entra. El valor se verifica contra
    # lo que la API realmente devuelve en lugar de asumirlo.
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    # Input cap of text-embedding-3-small. Every chunk is checked against this
    # BEFORE the first call: finding out when the API rejects it means paying
    # to learn it.
    # || Tope de entrada de text-embedding-3-small. Cada chunk se controla
    # contra esto ANTES de la primera llamada: enterarse cuando la API lo
    # rechaza es pagar por averiguarlo.
    EMBEDDING_MAX_INPUT_TOKENS: int = 8191

    EMBEDDING_BATCH_SIZE: int = 128
    EMBEDDING_MAX_RETRIES: int = 5

    # Seconds to wait before the first retry; doubles on each attempt.
    # || Segundos de espera antes del primer reintento; se duplica en cada intento.
    EMBEDDING_RETRY_BASE_DELAY: float = 1.0

    # How many batches to embed before persisting progress. A run that has to
    # start over on every network hiccup never finishes.
    # || Cuántos lotes se embeben antes de persistir el progreso. Una corrida
    # que hay que empezar de cero ante cada corte de red no termina nunca.
    EMBEDDING_CHECKPOINT_EVERY: int = 10

    # Binary sidecars (<module>.npy + <module>.index.json). Generated artifact,
    # outside the repository.
    # || Sidecars binarios (<module>.npy + <module>.index.json). Artefacto
    # generado, fuera del repositorio.
    EMBEDDINGS_PATH: Path = Path("data/embeddings")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (singleton).

    || Devuelve la configuración de la aplicación cacheada (singleton).
    """
    return Settings()

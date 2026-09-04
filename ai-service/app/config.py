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

    # Where the source markdown lives. `None` means the rebuild endpoint has
    # nothing to chunk and says so, instead of guessing a path.
    #
    # A setting and NOT a request parameter: accepting an arbitrary path over
    # HTTP is an arbitrary disk read by whoever can call the endpoint. The CLI
    # still takes `--root`, because there the caller already has the filesystem.
    # || Donde viven los markdown fuente. `None` significa que el endpoint de
    # rebuild no tiene nada que trocear y lo dice, en lugar de adivinar una ruta.
    #
    # Un setting y NO un parametro del request: aceptar una ruta arbitraria por
    # HTTP es una lectura de disco arbitraria de quien pueda llamar al endpoint.
    # La CLI sigue tomando `--root`, porque ahi quien llama ya tiene el disco.
    CORPUS_ROOT: Path | None = None

    # El bucket S3-compatible donde viven los documentos, cuando no estan en
    # disco. `CORPUS_BUCKET` es lo que decide cual de las dos fuentes se usa:
    # si esta puesto gana el bucket, y si no, `CORPUS_ROOT`.
    #
    # `S3_ENDPOINT_URL` es lo que hace que esto sirva para Railway, MinIO o
    # cualquier otro S3-compatible y no solo para AWS. Vacio significa AWS.
    # || The S3-compatible bucket where the documents live, when they are not on
    # disk. `CORPUS_BUCKET` is what picks the source: set, the bucket wins;
    # unset, `CORPUS_ROOT` does.
    #
    # `S3_ENDPOINT_URL` is what makes this work for Railway, MinIO or any other
    # S3-compatible service and not only AWS. Empty means AWS.
    CORPUS_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""
    # Vacias caen a la cadena de credenciales estandar de boto3 (variables
    # AWS_*, ~/.aws/credentials, rol de IAM). Verificado: pasarle None deja que
    # boto3 resuelva.
    # || Empty falls through to boto3's standard credential chain (AWS_* env
    # vars, ~/.aws/credentials, IAM role). Verified: passing None lets boto3
    # resolve.
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    # Vacia a proposito. boto3 NO necesita una region con un endpoint custom:
    # verificado, usa us-east-1 solo. Y el valor NO es decorativo -- es la region
    # con la que se firma SigV4, asi que inventar uno puede romper la
    # autenticacion contra un servicio que la valide. Solo se pone si el
    # proveedor pide una en concreto.
    # || Empty on purpose. boto3 does NOT need a region with a custom endpoint:
    # verified, it defaults to us-east-1 on its own. And the value is NOT
    # cosmetic -- it is the region SigV4 signs with, so inventing one can break
    # authentication against a service that validates it. Set it only if the
    # provider asks for a specific one.
    S3_REGION: str = ""

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

    # The reranker's model. NOT the bottleneck: `gpt-4o` scored exactly the same
    # +11 pairs as `gpt-4o-mini` on the run they were compared, at 5.6 s against
    # 3.3 s, so the cheap one is the default. What moved the number was telling
    # the model what a `_k` suffix means, not making the model bigger.
    # || El modelo del reranker. NO es el cuello de botella: `gpt-4o` saco
    # exactamente los mismos +11 pares que `gpt-4o-mini` en la corrida donde se
    # compararon, a 5,6 s contra 3,3 s, asi que el barato es el default. Lo que
    # movio el numero fue contarle al modelo que significa un sufijo `_k`, no
    # agrandar el modelo.
    RERANK_MODEL: str = "gpt-4o-mini"

    # Generation knobs. NOT the reranker's: ranking candidates and synthesizing
    # an answer are different jobs, and tuning one must not silently change the
    # other. The default MODEL is the same cheap one because there is no
    # measurement that justifies paying more; temperature and max tokens have
    # no reranker equivalent (that call returns ids, this one returns prose).
    # Temperature 0: insurance facts, not style. The fidelity eval has to be
    # able to reproduce a run.
    # || Perillas de generación. NO las del reranker: rankear candidatos y
    # sintetizar una respuesta son trabajos distintos, y tunear uno no tiene
    # que cambiar el otro en silencio. El MODEL default es el mismo barato
    # porque no hay medición que justifique pagar más; temperatura y max
    # tokens no tienen equivalente en el reranker (esa llamada devuelve ids,
    # esta devuelve prosa). Temperatura 0: hechos de seguros, no estilo. El
    # eval de fidelidad tiene que poder reproducir una corrida.
    ANSWER_MODEL: str = "gpt-4o-mini"
    ANSWER_MAX_TOKENS: int = 1024
    ANSWER_TEMPERATURE: float = 0.0

    # --- Proveedores de generación || Generation providers -----------------

    # Claves por proveedor. Sin clave, el proveedor se reporta NO disponible y
    # elegirlo falla en la consola con un mensaje claro, en vez de a la hora de
    # responder con un 500. `OPENAI_API_KEY` (más arriba) sirve además a los
    # embeddings y al reranker, que NO son multi-proveedor: las 57.101 filas
    # están en el espacio de `text-embedding-3-small` y un embedding de otro
    # proveedor no es comparable con ellas — cambiarlo es reconstruir el
    # corpus, no un setting.
    # || Per-provider keys. With no key the provider is reported unavailable
    # and picking it fails in the console with a clear message instead of at
    # answer time with a 500. `OPENAI_API_KEY` above also serves embeddings and
    # the reranker, which are NOT multi-provider: the 57,101 rows live in
    # `text-embedding-3-small` space and another provider's embedding is not
    # comparable to them.
    ANTHROPIC_API_KEY: str = ""
    MOONSHOT_API_KEY: str = ""

    # Master key con la que se cifran las credenciales que se guardan en la
    # base desde la consola (tabla `providers`). Vive en el ENTORNO y nunca en
    # la base: eso es lo que hace que un `pg_dump` filtrado se lleve ciphertext
    # y ninguna forma de leerlo.
    #
    # VACÍA = guardar credenciales está DESHABILITADO. A propósito no existe un
    # camino "por ahora en texto plano": así es como un dump termina con claves
    # vivas adentro. Las env vars de arriba siguen funcionando sin esto.
    # || Master key for credentials stored in the database from the console. It
    # lives in the ENVIRONMENT and never in the database, which is what makes a
    # leaked `pg_dump` carry ciphertext and no way to read it. EMPTY = storing
    # credentials is DISABLED; there is deliberately no plaintext fallback.
    SECRETS_KEY: str = ""

    # Moonshot (Kimi) sirve una API compatible con OpenAI, así que usa el mismo
    # adaptador con otro base_url. Hay dos endpoints según la región
    # (`api.moonshot.ai` internacional, `api.moonshot.cn` China): es un setting
    # y no una constante porque la elección no es del código.
    # || Moonshot (Kimi) serves an OpenAI-compatible API, so it reuses that
    # adapter with another base_url. Two endpoints exist by region, so this is
    # a setting and not a constant.
    MOONSHOT_BASE_URL: str = "https://api.moonshot.ai/v1"

    # El proveedor del `ANSWER_MODEL` de arriba. Un perfil de agente puede
    # sobreescribir el par (proveedor, modelo); esto es el default.
    # || The provider of `ANSWER_MODEL` above. An agent profile can override
    # the (provider, model) pair; this is the default.
    ANSWER_PROVIDER: str = "openai"

    # --- Perfiles de agente || Agent profiles ------------------------------

    # Los modelos que la consola ofrece para elegir por agente, como
    # `proveedor:modelo`. Una lista curada y no el catálogo de cada proveedor:
    # pedirle la lista completa devuelve decenas de modelos que no sirven para
    # esto (embeddings, audio, variantes viejas) y agrega una llamada de red al
    # render de un formulario. Env-overridable para no necesitar un deploy si
    # aparece uno nuevo.
    #
    # Los ids de Anthropic van SIN sufijo de fecha. Los de Moonshot conviene
    # verificarlos contra su catálogo vigente: cambian más seguido y esta lista
    # es justamente el lugar para ajustarlos sin tocar código.
    # || The models the console offers per agent, as `provider:model`. A curated
    # list, env-overridable. Anthropic ids carry NO date suffix. Moonshot's are
    # worth checking against their current catalog — this list is exactly where
    # to adjust them without touching code.
    ANSWER_MODEL_CATALOG: list[str] = [
        "openai:gpt-4o-mini",
        "openai:gpt-4o",
        "anthropic:claude-opus-5",
        "anthropic:claude-sonnet-5",
        "anthropic:claude-haiku-4-5",
        "moonshot:kimi-k2-0905-preview",
        "moonshot:moonshot-v1-8k",
    ]

    # Tope de la persona de un agente, el mismo que el curso (2000). Es texto
    # que entra en cada system prompt: sin tope, un pegado accidental de un
    # documento entero se paga en tokens en cada llamada.
    # || Cap on an agent's persona, the same as the course's (2000). It is text
    # that enters every system prompt: without a cap, an accidental paste of a
    # whole document is paid for in tokens on every call.
    AGENT_PERSONA_MAX_CHARS: int = 2000

    # Answer-orchestration graph (POST /answer/agentic). Separate from generation
    # knobs: the supervisor has its own step budget and human-review threshold.
    # || Grafo de orquestación (POST /answer/agentic). Separado de las perillas
    # de generación: el supervisor tiene su propio tope de pasos y umbral de
    # revisión humana.
    ANSWER_ORCHESTRATOR_MAX_STEPS: int = 12
    ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD: float = 0.6
    ANSWER_ORCHESTRATOR_MAX_REQUERIES: int = 1
    ANSWER_ORCHESTRATOR_PRIVILEGE_STRICT: bool = False
    ANSWER_ORCHESTRATOR_AUDIT_ARGS_PREVIEW_CHARS: int = 200

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

    # --- pgvector store || Store pgvector ----------------------------------

    # One URL for both stacks: the async engine swaps the driver token. The
    # default points at the local docker-compose service, whose credentials are
    # development-only; a deployment overrides this from its own environment.
    # || Una sola URL para los dos stacks: el engine async le cambia el driver.
    # El default apunta al servicio local de docker-compose, cuyas credenciales
    # son solo de desarrollo; un despliegue la sobreescribe desde su entorno.
    DATABASE_URL: str = "postgresql+psycopg://visualtime:visualtime@localhost:5432/visualtime_rag"

    # Postgres text-search configuration. Part of the schema, not a knob: the
    # generated column and its GIN index are built with it, so changing it means
    # a migration. Spanish because the corpus is Spanish -- with the English
    # stemmer `pólizas` and `póliza` do not collapse.
    # || Configuración de búsqueda de texto de Postgres. Es parte del esquema,
    # no una perilla: la columna generada y su índice GIN se construyen con
    # ella, así que cambiarla es una migración. Español porque el corpus es
    # español — con el stemmer inglés `pólizas` y `póliza` no colapsan.
    FTS_REGCONFIG: str = "spanish"

    # HNSW build parameters. pgvector's defaults (16 / 64); named here so a
    # rebuild is a settings change and not an edit inside a migration.
    # || Parámetros de construcción de HNSW. Los defaults de pgvector (16 / 64);
    # se nombran acá para que reconstruir sea un cambio de settings y no una
    # edición adentro de una migración.
    HNSW_M: int = 16
    HNSW_EF_CONSTRUCTION: int = 64

    # Rows per COPY batch when loading the corpus into Postgres.
    # || Filas por lote de COPY al cargar el corpus en Postgres.
    DB_COPY_BATCH_SIZE: int = 5000

    # --- Process map / CAG || Mapa de procesos / CAG -----------------------

    # Ceiling for the preloadable context. Over it, the build FAILS instead of
    # writing something that will be truncated in silence -- half a map reads
    # as a whole one. 128k leaves headroom inside a 200k window for the
    # question, the retrieved chunks and the answer.
    # || Techo del contexto precargable. Por encima, la construcción FALLA en
    # vez de escribir algo que se va a truncar en silencio — medio mapa se lee
    # como uno entero. 128k deja margen dentro de una ventana de 200k para la
    # pregunta, los chunks recuperados y la respuesta.
    CAG_MAX_TOKENS: int = 128_000

    PROCESS_MAP_PATH: Path = Path("data/process_map.json")
    CAG_CONTEXT_PATH: Path = Path("data/cag_context.md")

    # WITHOUT this, a filtered similarity search returns WRONG results, not slow
    # ones. HNSW walks its nearest candidates and only then applies the WHERE:
    # a query filtered by `transaction_type='query'` came back with 0 rows while
    # 7461 matched, because the filter discarded every candidate the index had
    # visited. Iterative scan (pgvector 0.8+) keeps scanning until it has enough
    # rows that pass. `strict_order` preserves exact distance ordering;
    # `relaxed_order` is faster but may not.
    # || SIN esto, una búsqueda por similitud con filtros devuelve resultados
    # EQUIVOCADOS, no lentos. HNSW recorre sus candidatos más cercanos y recién
    # después aplica el WHERE: una consulta filtrada por
    # `transaction_type='query'` devolvió 0 filas mientras 7461 cumplían, porque
    # el filtro descartó todos los candidatos que el índice había visitado. El
    # escaneo iterativo (pgvector 0.8+) sigue buscando hasta juntar suficientes
    # filas que pasen. `strict_order` conserva el orden exacto por distancia;
    # `relaxed_order` es más rápido pero puede no conservarlo.
    HNSW_ITERATIVE_SCAN: str = "strict_order"

    # Bounds the iterative scan so a filter that matches almost nothing cannot
    # walk the whole index.
    # || Acota el escaneo iterativo para que un filtro que casi no matchea nada
    # no pueda recorrer el índice entero.
    HNSW_MAX_SCAN_TUPLES: int = 20000


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (singleton).

    || Devuelve la configuración de la aplicación cacheada (singleton).
    """
    return Settings()

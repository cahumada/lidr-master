# Contexto del proyecto

## Qué es

Servicio IA (Python + FastAPI) que ingesta y trocea documentación funcional
del sistema **Visual Time** (seguros) para indexarla en un RAG con pgvector.
Proyecto final del Master AI Engineering (lidr).

El corpus fuente son documentos markdown de especificación funcional, uno por
transacción (`CA014`, `CA001`, ...), organizados en **30 módulos** de negocio
(`policies`, `life`, `claims`, `collections`, `maintenance`, ...) bajo una raíz
externa al repo (por defecto `D:\EspecificacionesFuncionales_md`). Tres
documentos reales viven en `ai-service/data/policies/` como fixtures de test.

## Layout del repo

Monorepo de dos proyectos, el layout que fija el programa del Master:

```
ai-service/         # el servicio Python + FastAPI (app/, scripts/, tests/, alembic/, data/, evals/)
business-backend/   # el frontend y backend de negocio: Next.js + Tailwind + shadcn/ui
openspec/           # la fuente de verdad — documenta los dos
scripts/            # herramientas del repo: hoy solo validate_specs.py
.github/workflows/  # CI: un job por proyecto, ninguno que despliegue
docker-compose.yml  # Postgres + pgvector para desarrollo local
```

`ai-service/` se despliega en Railway y `business-backend/` en Vercel, cada uno
por la integración nativa de su plataforma con GitHub.

**Las rutas de código en las specs del servicio IA son relativas a
`ai-service/`.** Una spec que dice `app/generation/rag/chunking/functional_spec.py`
se refiere a `ai-service/app/generation/rag/chunking/functional_spec.py`. El día
que una spec describa código de `business-backend/`, esa spec nombra su ruta
completa desde la raíz.

Lo que la mudanza a `ai-service/` **no** renombró, y no se debe "arreglar":

- La raíz del paquete Python sigue siendo `app.*`.
- `TENANT_ID` y `DOC_VERSION` conservan sus valores: están estampados en las
  57.101 filas de `chunks` y son parte de su clave única.
- La base sigue siendo `visualtime_rag`, el volumen de compose sigue siendo
  `pgdata` y el contenedor `visual-time-rag-postgres`.

`docker-compose.yml` se queda en la raíz por una razón concreta: el nombre del
proyecto de compose sale del directorio donde está el archivo. Moverlo a
`ai-service/` renombraría el volumen a `ai-service_pgdata` y levantaría una base
vacía, sin un solo error a la vista.

`scripts/validate_specs.py` es el único script que no vive en `ai-service/`:
deriva la raíz del repo de su propia ubicación para encontrar `openspec/`, que
documenta los dos proyectos. Es stdlib puro, así que corre con `python
scripts/validate_specs.py` desde la raíz, sin `uv` y sin `pyproject.toml` al
lado.

## Stack

### `business-backend/` — la consola web

- Next.js 16 (App Router) + TypeScript, React 19.
- **`pnpm`** para dependencias, fijado en `packageManager` de `package.json`,
  con `pnpm-lock.yaml` como el único lockfile del proyecto. CI corre
  `pnpm install --frozen-lockfile`, que falla si el lock no coincide con
  `package.json` — la misma propiedad que da `uv sync --frozen` del lado
  Python, y la que hace que la instalación sea reproducible en las dos stacks.
  pnpm 10 **no ejecuta los scripts de build** de las dependencias salvo que se
  listen en `pnpm.onlyBuiltDependencies`; acá no hay ninguno listado, y el
  único que los pide (`unrs-resolver`, transitivo de `eslint-config-next`)
  funciona igual porque su binario nativo llega precompilado por plataforma.
  Si algún día el lint falla por resolución de módulos, ese es el hilo.
- Tailwind v4 y **shadcn/ui**: el código de cada componente vive en
  `components/ui/`, no en `node_modules`. Se copian **solo los que se usan** —
  un `components/ui/` de cuarenta archivos para seis en uso es la versión
  shadcn de pre-construir capas vacías.
- **El tema es un artefacto generado, no CSS escrito a mano.** Los tokens de
  color, radio, sombras y tipografía de `app/globals.css` salen literales del
  registry item de un tema de tweakcn — hoy
  [`Woken`](https://tweakcn.com/themes/cmt3ah8fc000004id2kh74do2). Cambiar de
  tema es reemplazar los bloques `:root` / `.dark` enteros; un token retocado a
  mano se pierde en la próxima regeneración y nadie se entera hasta que el
  color vuelve solo.
- **Claro y oscuro son los dos de primera.** La clase `dark` en `<html>` la
  pone un script inline en `<head>`, antes del primer pintado, leyendo
  `localStorage` y cayendo a `prefers-color-scheme`. El servidor no puede saber
  el tema, así que corregirlo después de hidratar sería el flash blanco; toda
  la mecánica vive en `lib/theme.ts`, y ninguna pantalla puede dar por sentado
  un fondo claro.
- **Sin herramienta de monorepo de JS** (Turborepo, workspaces): hay una sola
  app JS, y una herramienta de monorepo para un paquete es el mismo ruido que
  una abstracción con una única implementación.
- **El browser nunca llama al servicio IA.** Todo sale del servidor, por los
  Route Handlers de `app/api/`; `lib/ai-service/base-client.ts` importa
  `server-only`, así que usarlo desde un Client Component es un error de build.
  `AI_SERVICE_URL` es privada, sin prefijo `NEXT_PUBLIC_`.
- **Una sola capa habla HTTP con el servicio**: `lib/ai-service/`, un cliente
  base más un cliente por contexto (`search`, `documents`, `corpus`). Los
  contextos no se importan entre sí y ninguna pantalla hace `fetch` por su
  cuenta.
- **Los tipos espejan los schemas Pydantic 1:1** (`lib/ai-service/types.ts`).
  Cuando el servicio agrega un campo, se agrega ahí primero.
- **Vercel AI SDK: todavía no.** El curso fija que el cliente nunca llama a un
  proveedor de modelos —toda la lógica de IA vive en el servicio— y acá no hay
  endpoint de generación que streamear. Entra cuando exista, y apuntado al
  Route Handler propio, sin claves de proveedor en esta app.

### `ai-service/` — el servicio IA

- Python 3.11, `uv` para dependencias y ejecución.
- FastAPI + Pydantic v2 (contratos tipados, visibles en Swagger).
- `structlog` para logging; `tiktoken` para conteo de tokens.
- `pytest` + `ruff` (line-length 100).
- SQLAlchemy 2.0 + Alembic + pgvector; psycopg3 para el `COPY` masivo y
  asyncpg para el camino de consulta.
- El chunking es determinístico y local: **ninguna API key es necesaria para
  trocear**. Sí lo son para embeber y para el reranker con modelo, y el reranker
  cae al léxico si no hay clave.

## Arquitectura por capas

Replica la arquitectura del curso (rama `session_16` de
[LIDR-academy/ai-engineering](https://github.com/LIDR-academy/ai-engineering/tree/session_16/ai-service/app),
donde el servicio vive en `ai-service/`, renombrado desde `estimator/` en la
sesión 15). Todo lo que sigue cuelga de `ai-service/`:

```
app/
├── config.py                                 # Settings (pydantic-settings) + get_settings() cacheado
├── dependencies.py                           # raíz de composición: singletons vía DI
├── main.py                                   # app FastAPI, structlog, routers
├── api/
│   ├── documents.py                          # ingesta (síncrona, sin persistir)
│   └── search.py                             # GET /search, con procedencia por hit
├── foundation/persistence/
│   └── database.py                           # Base, engines sync/async, settings de pgvector
└── generation/rag/
    ├── schemas.py                            # contratos Pydantic de esta arquitectura de generación
    ├── navigation.py                         # árbol de WINDOWS: módulos, tipos de ventana
    ├── taxonomy.py                           # clasificación por convención de nombres
    ├── chunking/                             # normalizer, functional_spec, base
    ├── embedding/                            # embedder, sidecar binario, runner reanudable
    ├── store/                                # models, loader (COPY), repository (3 caminos)
    ├── retrieval/                            # fusion (RRF), hybrid, decomposition, reranker
    └── process_map/                          # grafo de transacciones y contexto CAG
scripts/                                       # chunk, embed, load, build-map, evals
tests/generation/rag/                          # espeja la ruta del código que testea
```

Capas del curso deliberadamente **no** replicadas, y por qué:

- `app/ingestion/` — el pipeline batch dirigido por catálogo YAML del curso,
  con jobs en background y tracking en Postgres. Acá la ingesta batch existe
  pero como scripts (`chunk_corpus.py`, `embed_corpus.py`, `load_pgvector.py`),
  no expuesta por API ni con seguimiento de jobs. Lo que falta del curso es esa
  capa, no la lógica.

  **La razón original de esta decisión venció.** Decía «nuestra ingesta es
  síncrona, sin persistencia y sin catálogo», y la persistencia entró con
  pgvector. Lo que sigue siendo cierto es «sin catálogo» y un solo tipo de
  documento; la tabla de chunks por tipo de fuente del curso (`budget_chunks`,
  `transcript_chunks`, …) no aplica mientras haya uno solo.
- `app/foundation/` — el wrapper de LLM y los guardrails del curso. La
  persistencia SÍ entró (`app/foundation/persistence/`); lo que no hay todavía
  es el wrapper de LLM, porque la única llamada a modelo la hace el reranker y
  recibe su cliente inyectado.
- `app/generation/rag/chunking/base.py` existe pero **sin** la clase abstracta
  `Chunker` del curso: acá hay una sola estrategia, y una abstracción con una
  única implementación es ruido. Se agrega cuando entre la segunda estrategia.

**No pre-construir capas vacías**, y el registro muestra que funcionó: cuando
entraron los embeddings el lugar era `app/generation/rag/embedding/`, y cuando
entró pgvector era `app/foundation/persistence/`. Las dos capas se crearon con su
primer uso, no antes.

## Otros tipos de documento: la puerta queda abierta, la habitación no

A futuro se van a incorporar otros tipos de documento —contratos, condiciones de
póliza, lo que venga— y **todavía no están definidos**. Eso obliga a distinguir
dos cosas que se confunden fácil:

- **Decisiones persistidas.** Se toman ahora, porque cambiarlas después cuesta
  una migración. La identidad de una fila de `chunks` es
  `(tenant_id, doc_version, source_type, content_hash)`: `source_type` está en
  la clave única aunque hoy tenga un solo valor, `functional_spec`. Agregarlo
  después sería migrar la clave de 57.101 filas, hacer backfill y regenerar el
  corpus. Agregarlo hoy costó un `ALTER TABLE` con `server_default`.
- **Decisiones de código.** Se dejan para cuando el segundo tipo exista. El
  chunker está fijo en la firma de `_ingest()` y en `Depends(...)`; cambiarlo es
  mecánico y no compromete ningún dato. Y una abstracción diseñada para un
  formato que nadie vio todavía se diseña mal por definición — sigue valiendo
  «una abstracción con una única implementación es ruido».

Lo que **no** hace `source_type`: no arregla colisiones de texto entre
documentos, que ya eran imposibles porque el texto hasheado lleva el header
contextual `[Documento: CA014 - <título>]`. Medido sobre el corpus: 3.017 hashes
se repiten y **0** cruzan `document_id`. Sirve para dos cosas reales — que un
corpus mixto se pueda filtrar por clase de fuente, y que un tipo futuro que no
lleve un header así no colisione con este.

Regla práctica para lo que venga: **si la decisión queda escrita en la base, se
toma ahora; si vive solo en código, espera.**

## Convenciones de código

- **Identificadores en inglés**: clases, atributos, funciones, variables,
  claves de dict, y valores de `Literal` que sean identificadores de código
  (`"table"`, `"narrative"`, `"inline_transaction"`, `"footnote_tag"`).
- **Docstrings y comentarios bilingües**: primero inglés, luego ` || `, luego
  español, en el mismo bloque. Aplica también a `Field(description=...)`,
  porque ese texto se publica en Swagger.
- **Excepción — datos de dominio literales**: los nombres de sección que
  vienen del documento fuente en español (`"Función"`, `"Efecto"`, `"Notas
  para el programador"`, `"Campos"`, `"Validaciones"`, `"Introducción"`) se
  conservan en español como **valor**. Son el heading literal de la fuente,
  no un identificador; traducirlos rompería la trazabilidad hacia el texto.
  El *nombre de la clave* que los contiene sí va en inglés (`section`).
- **Sin `dict` pelado en un contrato expuesto**: un campo tipado como `dict`
  se renderiza como `object` vacío en la pestaña Schema de Swagger. Usar un
  `BaseModel` anidado (`ChunkMetadata`, `IngestStats`) para que los atributos
  reales sean visibles.
- Los routers no llevan lógica de negocio: solo transporte y mapeo de errores.

## Comandos

Los del servicio corren desde `ai-service/`:

```bash
cd ai-service
uv sync
uv run pytest
uv run ruff check .
uv run uvicorn app.main:app --reload
uv run python scripts/chunk_corpus.py --root "D:\EspecificacionesFuncionales_md" --out data/chunks
```

Los de la consola web, desde `business-backend/`:

```bash
cd business-backend
pnpm install
pnpm dev
pnpm lint
pnpm build
```

El validador de specs corre desde la raíz del repo, y sin `uv`:

```bash
python scripts/validate_specs.py
```

## Estado y alcance

Construido: normalización + reparación de tablas rotas, chunking híbrido (fila
de tabla vs. bullet narrativo), corrida batch sobre el corpus completo (2.169
archivos → 62.228 chunks), embeddings con sidecar binario, persistencia en
pgvector (57.101 filas), mapa de procesos y CAG, recuperación de tres caminos
con fusión RRF, descomposición de consultas compuestas, reranker, y tres
endpoints HTTP (`/documents/ingest`, `/documents/ingest-file`, `/search`).

Medido sobre 35 preguntas reales de usuarios: `p@10` 0,171 con 94% de hallazgo.

No construido todavía: **generación de respuestas** —la capa que falta para que
esto sea un RAG y no un buscador—, ingesta batch expuesta por API con
seguimiento de jobs, chunking jerárquico/semántico/con overlap, y el backend de
negocio.

Existe además, generado fuera de este repo, un corpus JSON enriquecido por
LLM para el módulo `policies` (`corpus_<tenant>_policies.json`, 174
unidades con resumen/keywords/referencias tipadas). No es consumido por este
pipeline todavía; la decisión de consumirlo o no está pendiente y debe pasar
por un `proposal.md`.

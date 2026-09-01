## Why

Hay 57.131 vectores en `data/embeddings/*.npy` y no se pueden consultar. Un
`.npy` se lee entero a memoria (351 MB) y no filtra por nada: para responder
*"validaciones de fecha de vigencia en el módulo de pólizas del cliente X,
versión Y"* hace falta un índice que combine similitud con filtros
estructurales. Eso es lo que falta.

Los datos para hacerlo ya están, y se pusieron ahí a propósito:

- `(tenant_id, doc_version, chunk_id)` es la clave compuesta que declaró
  `add-corpus-versioning`, y nunca se usó.
- `content_hash` identifica la fila y hace idempotente la carga.
- `module_code`, `transaction_type`, `document_kind`, `section` y `field` son
  los filtros que la búsqueda va a necesitar.

## What Changes

- **`app/foundation/persistence/`** — `database.py` con el engine y la sesión,
  y `Base`. Es el layout del curso (rama `session_16`), que separa la
  infraestructura de persistencia de la capa que la usa.
- **`app/generation/rag/store/`** — `models.py` (las tablas) y `repository.py`
  (la búsqueda), también como el curso.
- **Dos tablas.** `chunks` lleva el texto, el vector y todos los campos
  filtrables de `ChunkMetadata`. `corpus_versions` dice qué versión está
  vigente para cada cliente, con un índice único parcial que hace **imposible**
  tener dos activas a la vez.
- **Alembic**, con la extensión `vector` creada en la primera migración.
- **`scripts/load_pgvector.py`** — la carga masiva, por `COPY` de psycopg3
  leyendo el corpus JSON y el `.npy` mapeado a memoria. Idempotente por
  `(tenant_id, doc_version, content_hash)`: volver a correrla no duplica nada.
- **`docker-compose.yml`** con `pgvector/pgvector:pg17`, para que el que clone
  el repo pueda levantar la base con un comando.

## Tres adaptaciones sobre lo que hace el curso

**Una sola tabla de chunks, no una por tipo.** El curso tiene `budget_chunks`,
`transcript_chunks` y `technical_doc_chunks` porque ingiere tres clases de
fuente distintas. Acá hay una: especificaciones funcionales. Un mixin con una
sola implementación es la misma abstracción vacía que ya se descartó en
`chunking/base.py`.

**El full-text va en español.** El curso usa `regconfig = "english"`. Nuestro
corpus es español: con el stemmer inglés, `pólizas` y `póliza` no colapsan y
`de`/`la`/`el` no son stopwords. Sería un índice que no encuentra.

**`vector(1536)`, no `halfvec`.** El curso castea a `halfvec` porque el índice
HNSW de pgvector tolera hasta 2000 dimensiones con `vector` y hasta 4000 con
`halfvec`. 1536 entra holgado, y `halfvec` es media precisión: el ahorro de 175
MB no compra nada acá. Queda anotado como la salida si algún día sube la
dimensión.

## Capabilities

### Capability nueva

- `vector-store`: persistir los chunks con su vector y responder búsquedas por
  similitud con filtros estructurales, aislando cliente y versión.

## Impact

- `app/foundation/persistence/{__init__,database.py}` — nuevos.
- `app/generation/rag/store/{__init__,models.py,repository.py}` — nuevos.
- `app/config.py` — `DATABASE_URL`, parámetros del índice.
- `app/dependencies.py` — la sesión en la raíz de composición.
- `alembic/`, `alembic.ini`, `docker-compose.yml`, `scripts/load_pgvector.py`.
- `pyproject.toml` — `sqlalchemy`, `alembic`, `psycopg[binary]`, `asyncpg`,
  `pgvector`, `greenlet`.

## Los tests no pueden depender de Docker, y tampoco pueden mentir

pgvector no se puede emular: la distancia coseno, el índice HNSW y
`to_tsvector('spanish', ...)` son Postgres. Un doble en memoria testearía otra
cosa.

Pero la suite hoy corre en 3 segundos sin nada instalado, y eso vale.

**Se parte en dos.** Los tests que no necesitan base —construcción del SQL,
mapeo de fila a modelo, la planificación de la carga— siguen siendo unitarios y
corren siempre. Los que sí la necesitan quedan marcados `integration` y se
**saltean** si no hay una base alcanzable, con el motivo dicho en el skip.
`pytest` sigue verde y rápido; `pytest -m integration` corre contra la base real
que levanta el compose.

Un test que se saltea en silencio es peor que no tenerlo, así que el reporte
dice cuántos se saltearon y por qué.

## Lo que este cambio NO hace

- **No expone `/search`.** El endpoint necesita decisiones que todavía no están
  tomadas: diversidad por documento (una consulta genérica hoy devuelve 4 de 5
  chunks del mismo documento), fusión con el full-text, reranking. Es la
  capability `retrieval`, con su propio proposal.
- **No decide activar una versión.** Crea la tabla y la restricción que lo hace
  posible; activar es una operación, no un esquema.
- **No borra los `.npy`.** Siguen siendo la fuente reproducible desde la que se
  carga; la base es un índice, no el original.

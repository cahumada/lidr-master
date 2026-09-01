# Tareas de implementación

## 1. Infraestructura

- [x] 1.1 `sqlalchemy>=2.0`, `alembic>=1.13`, `psycopg[binary]>=3.1`,
      `asyncpg>=0.29`, `pgvector>=0.3`, `greenlet>=3.0` en `pyproject.toml`.
- [x] 1.2 `docker-compose.yml` con `pgvector/pgvector:pg17`, volumen nombrado y
      healthcheck.
- [x] 1.3 `DATABASE_URL` en `Settings` y en `.env.example`, con un default local
      que no lleve credenciales reales.
- [x] 1.4 `app/foundation/persistence/database.py`: `Base`, engine sync
      (psycopg) y async (asyncpg) desde la misma URL, y las factories de sesión.

## 2. Esquema

- [x] 2.1 `ChunkRow` con texto, `Vector(1536)`, `content_tsv` generada STORED en
      español, y los campos de `ChunkMetadata` en columnas.
- [x] 2.2 Única sobre `(tenant_id, doc_version, content_hash)`.
- [x] 2.3 `CorpusVersionRow` con índice único parcial sobre `tenant_id`
      restringido a las filas activas.
- [x] 2.4 Índices: HNSW `vector_cosine_ops`, GIN sobre `content_tsv`, btree
      sobre `(tenant_id, doc_version)` y sobre `document_id`.
- [x] 2.5 Alembic inicializado; la primera migración crea la extensión `vector`
      antes de las tablas.
- [x] 2.6 Test: el DDL que genera Alembic coincide con los modelos (sin drift).

## 3. Carga

- [x] 3.1 `scripts/load_pgvector.py`: corpus JSON + `.npy` mapeado a memoria,
      unidos por `content_hash`.
- [x] 3.2 `COPY` a temporal + `INSERT ... SELECT ... ON CONFLICT DO NOTHING`.
- [x] 3.3 `--dry-run` que informa filas a insertar, ya presentes y sin vector.
- [x] 3.4 Reportar los chunks sin vector en el sidecar en vez de inventarlos.
- [x] 3.5 Verificación post-carga: conteo, dimensión, ninguna fila en cero.

## 4. Repositorio

- [x] 4.1 `search()` async: k vecinos por coseno con filtros de cliente,
      versión, módulo y tipo.
- [x] 4.2 Los filtros se aplican como predicados, no filtrando después.
- [x] 4.3 Test unitario del SQL construido, sin base.

## 5. Tests

- [x] 5.1 Marca `integration` registrada en `pyproject.toml`.
- [x] 5.2 Fixture que saltea con el motivo si la base no responde.
- [x] 5.3 Integración: idempotencia, aislamiento por cliente y versión, una sola
      activa, stemming español, y que el plan use el índice HNSW.
- [x] 5.4 `pytest` sin base sigue verde y rápido.

## 6. Verificación y cierre

- [x] 6.1 Levantar la base, migrar y cargar los 57.131 chunks; medir.
- [x] 6.2 Una búsqueda real contra la base y contraste con la sonda sobre `.npy`.
- [x] 6.3 `pytest`, `pytest -m integration`, `ruff` y `validate_specs` en verde.
- [x] 6.4 Promover el delta y archivar.


## Resultados medidos

| | |
|---|---:|
| Filas cargadas | **57.101** |
| Documentos | 2.211 |
| Filas sin vector | 0 |
| Tabla + índices | 970 MB |
| Carga inicial | 159,9 s |
| Segunda corrida (idempotencia) | **0 filas**, 21,4 s |
| Búsqueda con filtros | 44–72 ms |

Postgres 17.11, pgvector 0.8.6. Tests: 310 con la base levantada, 292 + 18
salteados sin ella.

Los 62.228 chunks del corpus entran como 57.101 filas: un texto repetido es una
fila, igual que en el sidecar. La diferencia con las 57.131 del sidecar son los
30 duplicados **entre** módulos, que el sidecar guarda por separado porque es por
módulo y la tabla no.

## El bug que casi se publica, y que ningún doble en memoria habría mostrado

Una búsqueda filtrada por `transaction_type = 'query'` devolvió **0 filas
mientras 7.461 cumplían el filtro**. No es lentitud: son resultados equivocados.

HNSW recorre sus `ef_search` candidatos más cercanos y **recién después** aplica
el `WHERE`. Si el filtro descarta a todos los que visitó, el `LIMIT` se satisface
con nada. La misma consulta con `enable_indexscan = off` devolvía 10.

| `hnsw.iterative_scan` | hits | tiempo |
|---|---:|---:|
| `off` (default) | **0** | 6,8 ms |
| `relaxed_order` | 10 | 56,8 ms |
| `strict_order` | 10 | **48,2 ms** |

Se eligió `strict_order`: conserva el orden exacto por distancia y además
resultó más rápido. Va **en la conexión**, no en cada consulta — una consulta que
se lo olvide vuelve equivocada en silencio, y eso no puede depender de que quien
la escriba se acuerde.

Es la razón por la que estos tests tienen que correr contra Postgres de verdad.

## Correcciones sobre lo propuesto

- **El plan no siempre usa HNSW, y está bien.** Con un filtro selectivo el
  planner prefiere el btree del filtro más un sort exacto. La spec decía "el
  plan usa HNSW"; se corrigió a "cuando conviene", que es lo que se puede
  sostener.
- **El prune tenía que ser del corpus entero.** La primera versión podaba con la
  tabla de staging de **un** módulo, que no sabe nada de los otros 27: habría
  borrado 27/28 del corpus. Ahora recibe los hashes de todo y el batch rechaza
  `--prune` junto con `--module`.
- **`create_all` con `checkfirst` escribía en producción.** Con el `search_path`
  apuntando al esquema de test, el chequeo de existencia resolvía `chunks` al de
  `public` —el corpus real— y salteaba crear el de test. Los tests habrían
  escrito en la tabla real.

## Adaptaciones sobre el curso, confirmadas

- **Full-text en español.** Verificado: `to_tsvector('spanish', 'las pólizas de
  la póliza')` da `'poliz':2,5` — singular y plural colapsan y los artículos
  caen como stopwords. Con `english` no pasaría.
- **`vector(1536)` y no `halfvec`.** 1536 entra holgado en el límite de 2000 de
  HNSW; media precisión no compra nada acá.
- **Una tabla de chunks, no una por tipo de fuente.** El curso ingiere tres
  clases de documento; este proyecto una.

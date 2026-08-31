## Why

El corpus está troceado —61.901 chunks, 5.118.072 tokens, 2250 documentos— y
no sirve para nada hasta que sea buscable. La búsqueda semántica que el usuario
pidió ("encontrar transacciones relacionadas") necesita vectores; hoy no hay
ninguno.

El chunk ya está preparado para esto y no lo estamos usando:

- `content_hash` cubre **exactamente los bytes que se embeben** (`text`, header
  contextual incluido). Ese campo se agregó con un propósito declarado —
  *"si el hash coincide entre corridas, el embedding existente se reutiliza"*—
  y nunca se consumió.
- `(tenant_id, doc_version, chunk_id)` es la clave compuesta que va a ser la
  fila del índice vectorial.

**Por qué ahora y no directo a pgvector:** embeber y persistir son dos fallas
distintas. Si se hacen juntas, un error de conexión a Postgres a los 40 minutos
tira a la basura llamadas a la API ya pagadas. Separarlas hace que el paso caro
e irreversible (la llamada a OpenAI) se pueda repetir sin volver a pagarlo, y
que la persistencia sea un paso barato y reintentable sobre datos locales.

## What Changes

- **`app/generation/rag/embedding/`** — la capa que falta. Un protocolo
  `Embedder` y una implementación `OpenAIEmbedder` (`text-embedding-3-small`,
  1536 dims) con batching y reintentos con backoff exponencial.
- **Sidecar binario, no JSON.** Los vectores se escriben en `.npy` (float32),
  380 MB, junto a un índice JSON que mapea cada fila a su
  `(tenant_id, doc_version, chunk_id, content_hash)`. Inline en el corpus JSON
  serían ~1,8 GB de texto y volvería ilegible el artefacto que hoy se puede
  abrir y auditar a mano.
- **Reanudable por diseño.** El progreso se persiste por módulo; una corrida
  interrumpida se retoma donde quedó. Una corrida repetida sobre un corpus sin
  cambios no hace **ninguna** llamada a la API: el índice ya tiene el
  `content_hash` de cada fila.
- **Verificación explícita** al terminar: cantidad de filas == cantidad de
  chunks, dimensión == la declarada, ninguna fila en cero, y el índice alineado
  con el corpus. Un embedding silenciosamente vacío es peor que uno faltante.
- **`scripts/embed_corpus.py`** — el batch, con `--dry-run` que estima costo y
  llamadas sin gastar un centavo.
- **Embedder determinístico para tests.** La suite no toca la red ni necesita
  `OPENAI_API_KEY`.

## Capabilities

### Capability nueva

- `chunk-embedding`: generar y persistir el vector de cada chunk, de forma
  reanudable e incremental.

## Impact

- `app/generation/rag/embedding/{__init__,embedder.py,sidecar.py}` — nuevos.
- `app/generation/rag/schemas.py` — `EmbeddingIndexEntry`, `EmbeddingManifest`.
- `app/config.py` — `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`,
  `EMBEDDING_BATCH_SIZE`, `EMBEDDING_MAX_RETRIES`, `EMBEDDINGS_PATH`.
- `app/dependencies.py` — el embedder en la raíz de composición.
- `scripts/embed_corpus.py` — nuevo.
- `pyproject.toml` — `openai`, `numpy`.
- `data/embeddings/` — artefacto generado, **fuera del repo** (ya cubierto por
  `data/` en `.gitignore`).

## Lo que este cambio NO hace

- **No persiste en pgvector.** Es la fase 3, con su propio proposal: esquema de
  tabla, índice HNSW o IVFFlat, y la decisión de qué versión está activa.
- **No expone un endpoint de búsqueda.** Sin store no hay consulta.
- **No decide la estrategia de retrieval** (híbrido con BM25, reranking,
  expansión por `references`). El vector es el insumo de esa decisión, no la
  decisión.

## Números que justifican las elecciones

| | |
|---|---|
| Chunks a embeber | 61.901 |
| Tokens | 5.118.072 |
| Token máximo de un chunk | **500** (límite del modelo: 8191) |
| Costo estimado (`$0.02`/1M) | **US$ 0,10** |
| Tamaño del sidecar float32 | 380 MB |
| Mismo dato en JSON | ~1,8 GB |

El costo es bajo, pero la reanudabilidad no se justifica por el dinero sino por
el tiempo: 61.901 chunks en lotes de 128 son ~484 llamadas. A un ritmo
conservador eso son decenas de minutos, y una corrida que hay que empezar de
cero cada vez que se corta la red no se termina nunca.

Que el chunk más largo sea de 500 tokens no es casual —es el techo que impone
el chunker— pero **no se asume**: un chunk que exceda el límite del modelo se
detecta y se reporta antes de la primera llamada, no cuando la API lo rechaza.

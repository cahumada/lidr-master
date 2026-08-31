# Visual Time RAG — servicio IA

Pipeline de ingesta y chunking de documentos funcionales de Visual Time
(seguros), como paso previo a indexarlos en un RAG con pgvector.

## Puesta en marcha

```bash
uv sync
cp .env.example .env      # completar si vas a usar la capa de embeddings
uv run pytest
```

### Los datos NO están en el repo

`data/` está en `.gitignore`. Contiene documentación funcional y un export de
una tabla de producción que **pertenecen a un cliente**, más el corpus generado
(76 MB, reproducible en 12 s). El repo trae el pipeline, no los datos.

Para correrlo con un corpus propio:

```bash
uv run python scripts/chunk_corpus.py --root "RUTA/A/TUS/DOCUMENTOS" --out data/chunks --tenant mi_cliente --doc-version "mi version"
```

Los tests que usan documentos reales como fixture necesitan esos archivos en
`data/`; sin ellos fallan por archivo faltante, no por lógica.

Opcional, para resolver el breadcrumb Módulo → Submódulo → Transacción:

```bash
uv run --with xlrd python scripts/import_windows_tree.py "RUTA/Windows.xls"
```

Sin ese CSV el pipeline corre igual y deja el breadcrumb sin resolver.

## Fuente de verdad

Este repo documenta su comportamiento con [OpenSpec](https://github.com/Fission-AI/OpenSpec):

- **`openspec/specs/<capability>/spec.md`** — qué hace el sistema **hoy**. Es
  normativo: si el código y la spec no coinciden, uno de los dos tiene un bug.
- **`openspec/changes/`** — trabajo en curso; **`changes/archive/`** — por qué
  las cosas llegaron a ser como son (decisiones y alternativas descartadas).
- **`openspec/project.md`** — stack, arquitectura y convenciones.
- **[`AGENTS.md`](AGENTS.md)** — el ciclo de trabajo, agnóstico de modelo y de
  harness. `CLAUDE.md` y cualquier otro archivo de harness son punteros a ese.

```bash
uv run python scripts/validate_specs.py   # valida el formato de specs y changes
```

## Estructura

Replica la arquitectura por capas del curso (rama `session_16` de
[LIDR-academy/ai-engineering](https://github.com/LIDR-academy/ai-engineering/tree/session_16/ai-service/app)):

```
app/
├── config.py                                # Settings (pydantic-settings)
├── dependencies.py                          # composition root: singleton del chunker
├── main.py                                  # FastAPI app, structlog, routers
├── api/
│   └── documents.py                         # POST /documents/ingest (router delgado)
└── generation/rag/
    ├── schemas.py                           # Chunk, ChunkMetadata, Reference, IngestRequest/Response
    └── chunking/
        ├── base.py                          # count_tokens() (tiktoken, compartido)
        ├── normalizer.py                    # \r\n → \n, reparación de tablas rotas (export bug)
        └── functional_spec.py               # FunctionalSpecChunker: filas de tabla vs. bullets narrativos
```

No repliqué `app/ingestion/` del curso (catálogo YAML + jobs en background +
Postgres): esa capa es para otro tipo de fuente y trae infraestructura que
este endpoint no necesita (es síncrono y sin persistencia). La persistencia en
pgvector todavía no está — es la fase siguiente, con su propio proposal.

## Embeddings

`text-embedding-3-small` (1536 dims) sobre el corpus troceado. Los vectores van
a un **sidecar binario**, no inline en el corpus JSON: 380 MB en `.npy` float32
contra ~1,8 GB del mismo dato serializado como texto.

```bash
uv run python scripts/embed_corpus.py --dry-run
```

```bash
uv run python scripts/embed_corpus.py
```

La corrida es **incremental y reanudable**. Una fila se identifica por su
`content_hash`, nunca por su posición:

- hash en el sidecar y en el corpus → se reutiliza el vector
- hash solo en el corpus → se embebe
- hash solo en el sidecar → se descarta (su chunk ya no existe)

Volver a correr sobre un corpus sin cambios hace **cero** llamadas a la API. Un
lote que agota sus reintentos se reporta y la corrida sigue; el código de salida
es distinto de cero para que quien la invoque sepa que falta algo.

Sobre el corpus real: 61.901 chunks → **56.480 filas** (8,8% son texto repetido y
se embebe una sola vez), 4,76 M tokens, ~US$ 0,10.

## Uso

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Swagger en `http://localhost:8000/docs`. Dos endpoints:

- `POST /documents/ingest` — body JSON `{"filename": "...", "content": "..."}`.
  `content` es el **texto** del markdown, no una ruta — el servicio nunca lee
  del disco. Pensado para llamadores programáticos.
- `POST /documents/ingest-file` — subida de archivo (multipart). En Swagger
  aparece como un botón "Choose File" nativo; es la forma más cómoda de
  probar a mano con los `.md` de `data/policies/`.

```bash
curl -X POST http://localhost:8000/documents/ingest-file \
  -F "file=@data/policies/ca014.md;type=text/markdown"
```

## Tests

```bash
uv run pytest -v
```

`tests/generation/rag/test_normalizer.py` cubre el reparador de tablas
rotas contra 3 fixtures reales (CA014 "Ramos generales/Vida", las 2 tablas
"Tipo de registro/Transacción" de CA001, las 5 filas "Tipo de inicio de
vigencia/Fecha a mostrar" de CA001). `tests/generation/rag/test_functional_spec_chunker.py`
corre el chunker completo sobre los 3 documentos reales en `data/policies/`
(`ca001.md`, `ca004.md`, `ca014.md`), verificando el techo de ~500 tokens
por chunk narrativo, 1 chunk por fila de Campos/Validaciones, y la
extracción de referencias cruzadas (`` `CAC011` ``, `<DF009>`).

## Notas de diseño

- Clases y atributos en inglés; docstrings/comentarios bilingües (`EN || ES`).
- `metadata` (`ChunkMetadata`) y `stats` (`IngestStats`) son modelos
  Pydantic propios, no `dict` genéricos, para que Swagger muestre sus
  atributos reales tanto en "Schema" como en "Example Value".
- El id del documento se extrae solo del bloque de título (antes del primer
  `## `), para no confundirlo con referencias a otros documentos más abajo
  en el texto.
- No todos los documentos tienen `# ` en el título (CA014 no lo tiene); el
  extractor cae al primer renglón no vacío.
- Los nombres de sección (`Función`, `Efecto`, ...) se mantienen en español
  en `metadata.section`: son el heading literal del documento fuente, no
  identificadores de código — traducirlos rompería la trazabilidad.
- Chunking jerárquico/semántico avanzado, overlap y fixed-size splitting
  quedan deliberadamente fuera de alcance — la estructura del documento ya
  da los límites.

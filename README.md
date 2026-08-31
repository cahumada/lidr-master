# Visual Time RAG — servicio IA

Pipeline de ingesta y chunking de documentos funcionales de Visual Time
(seguros), como paso previo a indexarlos en un RAG con pgvector.

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
este endpoint no necesita (es síncrono y sin persistencia). Tampoco hay
embeddings ni persistencia en pgvector todavía — es una capa aparte
(`generation/rag/embedding/` en el curso), no construida.

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

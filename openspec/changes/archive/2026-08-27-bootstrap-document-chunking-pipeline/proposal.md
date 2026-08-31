## Why

El proyecto necesitaba un pipeline que convirtiera la documentación funcional
de Visual Time en chunks embebibles para un RAG. El repo arrancó vacío: no
había estructura, ni convenciones, ni un chunker.

El corpus real hacía inviable un chunking genérico por tamaño fijo. Validado
contra documentos reales:

- Las secciones narrativas (`Efecto`, `Notas para el programador`) varían de
  668 a 7.777 palabras entre documentos, con listas anidadas de 4-5 niveles —
  tratar cada sección H2 como un chunk único era imposible.
- `Campos` y `Validaciones` son tablas markdown donde cada fila es un hecho
  atómico (campo, regla, código de error).
- Algunos documentos traen un defecto de exportación: tablas cuyos
  encabezados quedaron como `####` y sin fila separadora, invisibles para
  cualquier parser de markdown.

Perder una celda de esas tablas es perder una regla de negocio de seguros, así
que el pipeline tenía que reparar el defecto y avisar, nunca fallar en silencio.

## What Changes

- Estructura del repo desde cero, replicando la arquitectura por capas del
  curso (rama `session_16` de LIDR-academy/ai-engineering): `config.py`,
  `dependencies.py`, `main.py`, `api/`, `generation/rag/`.
- Normalizador: `\r\n` → `\n` y reparación de las dos formas de tabla rota
  encontradas en el corpus, con trazabilidad y advertencia al rellenar celdas.
- Chunker híbrido: fila por chunk en secciones que son tablas puras, y bullet
  de primer nivel con sus hijos (con techo de tokens y descenso recursivo) en
  secciones narrativas. Contextual header en todo chunk. Referencias cruzadas
  con discriminador de tipo.
- Detección de secciones genérica: cualquier heading H2, en vez de una lista
  fija de cinco nombres, para cubrir los 30 módulos del corpus.
- Dos endpoints HTTP: `POST /documents/ingest` (body JSON) y
  `POST /documents/ingest-file` (subida de archivo, para probar desde Swagger).
- Contratos tipados (`ChunkMetadata`, `IngestStats`) en vez de `dict` pelado,
  para que Swagger muestre los atributos reales.
- Script de corrida batch sobre el corpus completo, con reporte por módulo y
  aislamiento de fallas.
- Convención de código: identificadores en inglés, docstrings y comentarios
  bilingües `EN || ES`.

## Capabilities

### Capabilities nuevas

- `table-repair`: normalización de texto y reparación del defecto de
  exportación de tablas, con trazabilidad y advertencias.
- `document-chunking`: chunking híbrido guiado por la forma del contenido,
  con techo de tokens, contextual header y extracción de referencias.
- `document-ingestion-api`: los dos endpoints de ingesta y el contrato de
  respuesta tipado.
- `corpus-batch-chunking`: corrida batch sobre los 30 módulos con reporte de
  anomalías.

## Impacto

- `app/config.py`, `app/dependencies.py`, `app/main.py` — raíz de composición.
- `app/api/documents.py` — los dos endpoints.
- `app/generation/rag/schemas.py` — contratos Pydantic.
- `app/generation/rag/chunking/{base,normalizer,functional_spec}.py` — el pipeline.
- `scripts/chunk_corpus.py` — corrida batch.
- `tests/generation/rag/` — 26 tests sobre fixtures y documentos reales.
- `pyproject.toml` — fastapi, pydantic, structlog, tiktoken, python-multipart.
- `data/policies/` — tres documentos reales como fixtures.

## Nota sobre este registro

Este cambio se documentó **retroactivamente**, al adoptar OpenSpec después de
que el trabajo ya estaba hecho y verificado. No conserva archivos de delta:
las cuatro capabilities que creó están descritas completas en
`openspec/specs/`, y duplicar ese texto acá crearía dos copias que se
desincronizarían. Los cambios de acá en adelante sí siguen el ciclo completo
(proposal → implementación → archivo con sus deltas), según
`openspec/AGENTS.md`.

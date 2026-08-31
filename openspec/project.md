# Contexto del proyecto

## Qué es

Servicio IA (Python + FastAPI) que ingesta y trocea documentación funcional
del sistema **Visual Time** (seguros) para indexarla en un RAG con pgvector.
Proyecto final del Master AI Engineering (lidr).

El corpus fuente son documentos markdown de especificación funcional, uno por
transacción (`CA014`, `CA001`, ...), organizados en **30 módulos** de negocio
(`policies`, `life`, `claims`, `collections`, `maintenance`, ...) bajo una raíz
externa al repo (por defecto `D:\EspecificacionesFuncionales_md`). Tres
documentos reales viven en `data/policies/` como fixtures de test.

## Stack

- Python 3.11, `uv` para dependencias y ejecución.
- FastAPI + Pydantic v2 (contratos tipados, visibles en Swagger).
- `structlog` para logging; `tiktoken` para conteo de tokens.
- `pytest` + `ruff` (line-length 100).
- Sin LLM y sin base de datos en esta capa: el chunking es determinístico y
  local. Ninguna API key es necesaria para trocear.

## Arquitectura por capas

Replica la arquitectura del curso (rama `session_16` de
[LIDR-academy/ai-engineering](https://github.com/LIDR-academy/ai-engineering/tree/session_16/ai-service/app),
donde el servicio vive en `ai-service/`, renombrado desde `estimator/` en la
sesión 15):

```
app/
├── config.py                                 # Settings (pydantic-settings) + get_settings() cacheado
├── dependencies.py                           # raíz de composición: singletons vía DI
├── main.py                                   # app FastAPI, structlog, routers
├── api/
│   └── documents.py                          # routers delgados (solo transporte + mapeo de errores)
└── generation/rag/
    ├── schemas.py                            # contratos Pydantic de esta arquitectura de generación
    └── chunking/
        ├── base.py                           # count_tokens() compartido
        ├── normalizer.py                     # fin de línea + reparación de tablas rotas
        └── functional_spec.py                # FunctionalSpecChunker (una estrategia = un archivo)
scripts/
├── chunk_corpus.py                           # corrida batch sobre los 30 módulos
└── validate_specs.py                         # validador de openspec/
tests/generation/rag/                         # espeja la ruta del código que testea
```

Capas del curso deliberadamente **no** replicadas, y por qué:

- `app/ingestion/` — el pipeline batch dirigido por catálogo YAML del curso,
  con jobs en background y tracking en Postgres. Nuestra ingesta es síncrona,
  sin persistencia y sin catálogo; replicarla sería infraestructura sin uso.
- `app/foundation/` — wrapper de LLM, guardrails, persistencia. No hay
  llamadas a LLM ni base de datos en esta capa todavía.
- `app/generation/rag/chunking/base.py` existe pero **sin** la clase abstracta
  `Chunker` del curso: acá hay una sola estrategia, y una abstracción con una
  única implementación es ruido. Se agrega cuando entre la segunda estrategia.

No pre-construir capas vacías. Cuando entre embeddings, el lugar es
`app/generation/rag/embedding/`; cuando entre pgvector,
`app/foundation/persistence/`.

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

```bash
uv sync
uv run pytest
uv run ruff check .
uv run python scripts/validate_specs.py
uv run uvicorn app.main:app --reload
uv run python scripts/chunk_corpus.py --root "D:\EspecificacionesFuncionales_md" --out data/chunks
```

## Estado y alcance

Construido: normalización + reparación de tablas rotas, chunking híbrido
(fila de tabla vs. bullet narrativo), dos endpoints HTTP, corrida batch sobre
el corpus completo (2169 archivos → ~67k chunks).

Fuera de alcance en esta capa (capas separadas, no construidas): embeddings,
persistencia en pgvector, búsqueda semántica, chunking
jerárquico/semántico/con overlap, y el backend de negocio.

Existe además, generado fuera de este repo, un corpus JSON enriquecido por
LLM para el módulo `policies` (`corpus_life_seguros_policies.json`, 174
unidades con resumen/keywords/referencias tipadas). No es consumido por este
pipeline todavía; la decisión de consumirlo o no está pendiente y debe pasar
por un `proposal.md`.

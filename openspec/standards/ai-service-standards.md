# Estándares del servicio IA

Convenciones del API Python en `ai-service/`. No cubre el BFF de Next —
eso es [bff-standards.md](./bff-standards.md). Las rutas de código en este
documento son relativas a `ai-service/`.

## Stack

| Capa | Tecnología |
|---|---|
| Runtime | Python 3.11 |
| Dependencias | `uv` (`uv.lock` es la fuente; CI instala con `uv sync --frozen`) |
| HTTP | FastAPI + Pydantic v2 |
| Config | `pydantic-settings`, `get_settings()` cacheado en `app/config.py` |
| Logs | `structlog` (JSON en production, consola en desarrollo) |
| Persistencia | SQLAlchemy 2.0 + Alembic + pgvector; psycopg3 para COPY, asyncpg para consulta |
| LLM | Wrapper en `app/foundation/llm/`; el cliente se arma en DI, no en el feature |
| Prompts | Jinja2 versionados en `app/foundation/prompts/<name>/vN/` |
| Tests | `pytest` + `httpx` (`TestClient`) |
| Lint | `ruff` (line-length 100, target py311) |

Comandos, desde `ai-service/`:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run uvicorn app.main:app --reload   # Swagger en /docs
```

## Arquitectura

Composition root en `app/main.py` (app, logging, routers, lifespan) y
`app/dependencies.py` (singletons). Los routers son transporte.

```
app/
├── config.py
├── dependencies.py          # DI: chunker, embedder, retriever, …
├── main.py
├── api/                     # routers delgados
├── foundation/
│   ├── persistence/         # engines, sessions, Base
│   ├── llm/                 # wrapper multi-proveedor
│   └── prompts/             # templates versionados
├── generation/
│   ├── rag/                 # chunking, embedding, store, retrieval, answer
│   └── conversation/        # memoria (hechos, anchors, turnos) + history
├── domain/                  # grafo, perfiles, catálogo de agentes
└── ingestion/               # pipeline batch y jobs de corpus
```

**No pre-construir capas vacías.** Una abstracción con una sola
implementación es ruido. La segunda estrategia (otro chunker, otro
store) es el momento de extraer la interfaz.

**Los routers no llevan lógica de negocio.** Orquestan Depends, mapean
errores a `HTTPException`, devuelven un `response_model`. El retrieve,
el generate, el guardrail y el store viven abajo.

```python
# Good — transporte
@router.post("", response_model=AnswerResponse)
async def answer(body: AnswerRequest, session: AsyncSession = Depends(get_async_session)):
    retriever = HybridRetriever(ChunkRepository(session), get_embedder())
    return await generate_answer(...)

# Avoid — prompt, llamada LLM o chequeo de citas adentro del router
```

## SOLID y DRY, aplicados acá

No hay un DDD de entidades `Candidate`. El dominio es el corpus, la
recuperación y el grafo de respuesta. Los principios se leen sobre
*este* código:

**SRP.** Un router no chunk-ea. Un chunker no habla HTTP. El guardrail
de citas vive junto a la generación porque su único consumidor es esa
capa — no se sube a `foundation/` “por si acá”.

**OCP.** Un proveedor nuevo es una fila + un wire ya implementado, no
un `if provider ==` en el sintetizador. Los agentes se eligen por
catálogo (`AGENT_SPECS`), no por un switch en el router.

**LSP.** Un test double del embedder sustituye a `OpenAIEmbedder` sin
que el retriever se entere. Por eso el cliente OpenAI se construye en
`get_embedder()`, no dentro del retriever.

**ISP.** `get_embedder` y `get_reranker` son factories distintas. Un
endpoint que no rerankea no arrastra el reranker.

**DIP.** `app/dependencies.py` es el composition root. Los routers
piden abstracciones por `Depends`. En tests se overridea
`app.dependency_overrides` o se monkeypatchea la clase en el módulo
del router (`HybridRetriever`).

**DRY.** `_ingest` es el cuerpo compartido de `/documents/ingest` y
`/ingest-file`. `_as_job` mapea la fila al schema una sola vez. Si un
default de query param se declara en FastAPI, el BFF no lo vuelve a
declarar.

## Contratos

- Schemas Pydantic, no `dict`. Un `dict` se renderiza como `object`
  vacío en Swagger.
- `Field(description=...)` bilingüe.
- Un archivo fuente puede describir varias transacciones: las respuestas
  de ingesta llevan `documents: list`, nunca un shape distinto para el
  caso de uno.
- Validación en el borde: `Query(min_length=2)`, `ge` / `le`, modelos
  de request. El router no re-valida a mano lo que Pydantic ya rechaza
  con 422.

```python
# Good
class IngestStats(BaseModel):
    total_documents: int
    total_chunks: int
    table_chunks: int
    narrative_chunks: int

# Avoid
stats: dict  # Swagger muestra additionalProp1
```

## Errores y logs

- `HTTPException` con `detail` en inglés (o bilingüe si el detalle es
  para un operador que lee Swagger). El BFF aplana `detail` a una línea
  y la muestra en español cuando traduce.
- Status que son *estado*, no falla: `202` en rebuild y en el gate
  humano; `409` cuando ya hay un job corriendo. No convertirlos en 500.
- `structlog` con contexto: `filename`, `document_id`, `error_type`.
  Nunca loguear una API key ni el body de `PUT /config/providers/{id}/key`.

```python
log.info("documents_ingest_done", filename=filename, **stats.model_dump())
log.error("documents_ingest_failed", filename=filename, error_type=type(exc).__name__)
```

## Persistencia

- Identidad de un chunk: `(tenant_id, doc_version, source_type, content_hash)`.
  `source_type` está en la clave aunque hoy tenga un solo valor. Si la
  decisión queda escrita en la base, se toma ahora; si vive solo en
  código, espera.
- Migraciones por Alembic. No reformatear `alembic/versions/` (ruff las
  excluye). `alembic/env.py` inserta `sys.path` *antes* de importar `app`.
- El pipeline de corpus lee un directorio local o un bucket. La raíz
  sale de `Settings.CORPUS_ROOT`, **nunca** de un parámetro HTTP
  (lectura arbitraria de disco).
- `TENANT_ID` y `DOC_VERSION` están estampados en las filas de `chunks`.
  No “arreglarlos” a un default nuevo sin una rebuild consciente.

## Prompts y proveedores

- Prompts versionados bajo `app/foundation/prompts/`. `StrictUndefined`:
  una variable faltante falla, no renderiza vacío.
- Nada de strings de system/user hardcodeados en un feature service, ni
  interpolar input no confiable adentro del template.
- Llamar modelos solo por `app/foundation/llm/`. Un feature no importa
  el SDK del vendor. El cliente se arma en DI.
- Credenciales: `PUT /config/providers/{id}/key` es write-only. Ningún
  GET devuelve la clave. Una env var le gana a la clave guardada.

## Tests

Los tests espejan la ruta del código: `tests/generation/rag/` prueba
`app/generation/rag/`. Los de contrato HTTP viven en `tests/api/`.

- **Unidad** — chunker, guardrails, fusión, hechos de conversación.
  Sin red y sin base.
- **Router** — `TestClient`, dependencias overrideadas, retriever
  falso. Se prueba el contrato (procedencia, defaults, 422), no la
  calidad de la búsqueda.
- **Integración** — store y pipeline cuando hay `DATABASE_URL`. Si no
  hay base, el test se *salta* y lo dice. CI no levanta Postgres a
  propósito.
- **Eval** — `p@10` y fidelidad de citas no son asserts de pytest;
  viven en `evals/` y en scripts. No meter el golden set en un unit
  test.

Patrón AAA, nombres que describen el comportamiento:

```python
def test_a_hit_carries_its_provenance(client, monkeypatch):
    # Arrange — retriever falso inyectado por el fixture
    # Act
    body = client.get("/search", params={"q": "limites de capital"}).json()
    # Assert
    assert body["hits"][0]["document_id"] == "CA014"
    assert "vector" in body["hits"][0]["branches"]
```

Categorías mínimas por función nueva: happy path, error / 422, borde
(lista vacía, session vencida), y el mapping de status especiales
(202, 409) cuando el endpoint los usa.

Mockear I/O. No pegarle a OpenAI ni a la base en un unit test. El
embedder se sustituye; el retriever se monkeypatchea en el módulo del
router.

## Seguridad

- Validar en el contrato. No hacer spread de un JSON crudo a un modelo
  SQLAlchemy.
- `CORPUS_ROOT` y paths de filesystem no se aceptan por HTTP.
- Secretos en `.env`, nunca en git. `.env.example` es la plantilla.
  Validar settings al arrancar lo que *hace falta* para ese proceso;
  el seeding de proveedores es best-effort y no tumba `/health`.
- Minimizar respuestas: DTO, no la fila ORM. Hint de cuatro caracteres
  para claves, nunca el valor.
- El servicio no tiene auth de usuario hoy. No agregar un middleware
  de “por las dudas” ni CORS permisivo “para la consola”: la consola
  habla por el BFF, same-origin, y `AI_SERVICE_URL` es privada.

## Performance

- `async` en el camino de consulta. El COPY masivo es sync a
  propósito (psycopg3).
- No bloquear el lifespan con trabajo remoto: el seed de proveedores
  corre en background para no atrasar `/health` ni `/docs`.
- Rebuild es 202 + job. Embeber un corpus no cabe en un request.
- `Promise`-equivalente: `asyncio.gather` solo cuando las partes no
  se necesitan entre sí.

## Workflow de este stack

- Rama con sufijo `-ai-service`. Ver [git-workflow.md](./git-workflow.md).
- `uv run ruff check .` y `uv run pytest` antes de dar el change por
  listo. Un check en rojo no se mergea.
- Nueva dependencia: justificarla en el `proposal.md`. El lockfile
  viaja en el mismo commit.

## Despliegue (Railway)

El servicio se despliega en **Railway**, no en Vercel. La consola
(`business-backend/`) es el otro proyecto y va a otra plataforma.

- **Root directory** `ai-service/`. El contexto de build es ese
  directorio: `ai-service/Dockerfile` no ve `business-backend/` ni
  `openspec/`.
- **Imagen:** `Dockerfile` (Python 3.11-slim + `uv sync --frozen`).
  El lockfile tiene que coincidir con `pyproject.toml` o el build
  falla — la misma propiedad que CI.
- **Healthcheck:** `GET /health`. El lifespan no puede bloquearlo
  (el seed de proveedores corre en background).
- **Watch Paths:** `ai-service/**`. Un commit que solo toca la
  consola o `openspec/` no redespliega el servicio.
- **Secretos** en las variables del servicio de Railway, no en el
  repo. `.env.example` es la plantilla. Una env var le gana a una
  clave guardada desde la consola.
- CI (`.github/workflows/ci.yml`) **no** despliega. El merge a
  `main` que toca `ai-service/` es lo que dispara Railway.

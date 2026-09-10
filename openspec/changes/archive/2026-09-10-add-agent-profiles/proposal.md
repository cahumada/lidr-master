## Why

El curso permite configurar por UI la **personalidad** de cada agente y **sobre
qué modelo** trabaja (`Agents::Profile`: `name`, `persona` que se appendea al
system prompt, `avatar`, y un `config` JSONB con `model`,
`reasoning_effort`, `max_iterations`, `search_top_k`,
`search_distance_threshold`; más `Agents::GraphFlow::NODES`, un catálogo de
nodos con su modelo y su `config_key`). Acá no existía nada de eso: un knob por
concern en `config.py` (`ANSWER_MODEL`, `ANSWER_TEMPERATURE`,
`ANSWER_MAX_TOKENS`), un prompt fijo sin persona, y ninguna pantalla.

**El hueco es parcialmente de diseño, no un olvido.** De los seis nodos del
grafo, **uno solo llama a un modelo**: `answer_synthesizer`. `query_planner`
(regex + `decompose()`), `evidence_retriever` (la tool de retrieval) y
`citation_validator` (`check_grounding`) son deterministas a propósito — es lo
que mantiene reproducibles los números de las evaluaciones medidas. En el curso
casi todos los nodos son LLM-driven, y por eso allá "modelo y persona por
agente" significa algo en cinco nodos y acá en uno. Este change **no** revierte
esa decisión: la expone.

## What Changes

- `ai-service`: catálogo de agentes en `app/domain/graph/catalog.py` — clave,
  label, rol, explicación, `kind`, `llm_driven` y el setting que da sus
  defaults. `tools` se **deriva** de `AGENT_PRIVILEGES` en vez de repetirse.
- `ai-service`: tabla `agent_profiles` (una fila por agente) con `persona`,
  `model`, `temperature`, `max_tokens`, todos nullable. Un knob ausente
  significa "usar el default del servicio" — la misma semántica que el
  `config_payload` del curso.
- `ai-service`: `GET /config` sirve el catálogo con la configuración vigente de
  cada agente y **de dónde salió cada valor** (`profile` vs `settings`), más el
  catálogo de modelos y el tope de persona. `PUT`/`DELETE
  /config/agents/{agent_key}` escriben y limpian el perfil.
- `ai-service`: la persona se appendea al system prompt `answer/v1` **después**
  de las reglas de grounding y subordinada a ellas de forma explícita. Sin
  persona el prompt se renderiza byte-idéntico al anterior, así el eval de
  fidelidad sigue siendo comparable.
- `ai-service`: `synthesizer_runtime(session, settings)` es el único punto por
  el que los tres caminos de síntesis (`POST /answer`, `POST /answer/agentic`,
  el runner en background) resuelven LLM y persona, así un perfil no puede
  aplicar a uno y no a los otros. El grafo los recibe por su config; el agente
  no lee la base.
- `business-backend`: pantalla `/agents` que arma todo desde `GET /config`, con
  formulario de persona/modelo/temperatura/tope para el agente configurable y
  fichas read-only para los deterministas, diciendo por qué no aplican.
- `alembic/env.py`: `include_name` excluye las tablas del checkpointer de
  LangGraph de la comparación. **Encontrado en este change:** el primer
  autogenerate proponía `drop_table` sobre `checkpoints`,
  `checkpoint_writes`, `checkpoint_blobs` y `checkpoint_migrations` —
  correrlo habría borrado cada hilo pausado esperando revisión humana.

### Deliberadamente descartado (con razón)

- **Hacer LLM-driven a los agentes deterministas** para que la persona tenga
  efecto en más de uno: revierte una decisión de diseño medida (costo,
  latencia, y los números de los evals dejan de ser comparables). Si algún día
  se hace, es su propio change con su propia medición.
- **`avatar`, `is_default` y varios perfiles por agente** (del curso): la
  identidad visual no cambia ninguna respuesta, y "varios perfiles con uno
  default" es una feature de producto para elegir entre configuraciones
  guardadas. Con un agente configurable, una fila por agente alcanza.
- **`reasoning_effort`, `max_iterations`, `search_top_k`,
  `search_distance_threshold`** (los otros knobs del curso): `max_iterations` y
  los de búsqueda ya existen acá como `ANSWER_ORCHESTRATOR_MAX_STEPS`,
  `ANSWER_ORCHESTRATOR_MAX_REQUERIES` y los parámetros por request de
  `/search`; `reasoning_effort` no aplica a los modelos del catálogo. Exponer
  un knob que el servicio ignora sería peor que no tenerlo.

## Capabilities

### New Capabilities

- `agent-profiles`: catálogo de agentes servido por el servicio y overrides de
  persona y modelo por agente, con validación de que solo se configura lo que
  tiene efecto.

### Modified Capabilities

- `answer-orchestration`: el LLM y la persona del sintetizador salen de su
  perfil, resueltos en un único punto para los tres caminos de síntesis.

## Impact

- `ai-service/app/domain/graph/catalog.py` (nuevo)
- `ai-service/app/domain/profiles.py` (nuevo)
- `ai-service/app/api/config.py` (nuevo)
- `ai-service/alembic/versions/b15380641ff9_*.py` (nueva tabla), `alembic/env.py`
- `ai-service/app/config.py` — `ANSWER_MODEL_CATALOG`, `AGENT_PERSONA_MAX_CHARS`
- `ai-service/app/dependencies.py` — `build_answer_llm`, `_openai_client`
- `ai-service/app/foundation/prompts/answer/v1/system.j2` — bloque de persona
- `ai-service/app/generation/rag/prompt_builder.py`, `answer.py` — `persona`
- `ai-service/app/api/answer.py`, `answer_agentic.py`,
  `app/domain/graph/runner.py`, `agents/answer_synthesizer.py` — wiring
- `ai-service/tests/domain/test_profiles.py`,
  `tests/domain/graph/test_catalog.py`, `tests/api/test_config_router.py`
  (nuevos); `tests/api/conftest.py`, `tests/api/test_answer_router.py`,
  `tests/generation/rag/test_prompt_builder.py`
- `business-backend/app/agents/`, `app/api/config/`,
  `lib/ai-service/config.ts`, `types.ts`, `base-client.ts`, `layout.tsx`,
  `page.tsx`
- `openspec/changes/add-agent-profiles/specs/agent-profiles/spec.md`

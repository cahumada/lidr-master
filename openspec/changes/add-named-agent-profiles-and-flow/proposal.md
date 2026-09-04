## Why

En el curso ([`agents_event` / `app/views/agents`](https://github.com/LIDR-academy/ai-engineering/tree/agents_event/business-backend/app/views/agents))
se **crea** un agente como perfil nombrado (`Agents::Profile`: nombre,
persona, modelo, `is_default`) y se **mira** el flujo en
`agents/graph_flow` (`Agents::GraphFlow::NODES`). Acá `/agents` solo edita
una fila anónima por nodo del grafo: no hay nombre, no hay varios presets,
no hay pantalla de flujo. Quien viene del master no encuentra dónde
«crear un agente» ni dónde «armar el flujo».

`add-agent-profiles` ya cerró el hueco mínimo (persona + modelo del
sintetizador) y **descartó** a propósito varios perfiles nombrados: con un
solo agente LLM-driven, una fila por `agent_key` alcanzaba. Eso dejó la
consola correcta para overrides, pero incompleta respecto de la UX del
curso. El dueño ahora pide esa UX.

**Qué no es este change.** No es un editor de grafo. En el curso
`GraphFlow` es prosa estática y **no cambia el flujo**; acá el catálogo ya
vive en el servicio para no divergir. Crear un *nodo* nuevo (otro
especialista, otra tool, otra arista) sigue siendo código — un setting
que el dispatcher no aplica sería un override que no hace nada, y eso
`add-agent-profiles` ya rechaza.

## What Changes

- `ai-service`: `agent_profiles` pasa de «una fila por `agent_key`» a
  **perfiles nombrados** por agente configurable: `name`, `persona`,
  `provider`, `model`, `temperature`, `max_tokens`, `is_default`. Un knob
  nulo sigue significando «default del servicio». La fila anónima que
  ya exista se migra a un perfil default llamado a partir de su persona o
  `"Default"`.
- `ai-service`: CRUD `POST/PUT/DELETE /config/agents/{key}/profiles[/{id}]`.
  `GET /config` lista los perfiles de cada agente configurable y marca
  cuál es el default. Siguen valiendo 404 (agente desconocido), 422
  (determinista / modelo oculto / persona sobre el tope).
- `ai-service`: `synthesizer_runtime` resuelve el perfil **default** del
  sintetizador. `POST /answer` y `POST /answer/agentic` aceptan un
  `profile_id` opcional para esa corrida; ausente = default. Un id que no
  pertenece a `answer_synthesizer` se rechaza con 422.
- `ai-service`: `GET /config` (o un campo suyo) expone la **topología**
  del grafo — nodos, `kind`, aristas de salida, orden de la escalera —
  derivada del catálogo y de `build.py` / `_ORDER`, no reescrita en
  TypeScript. La consola de flujo no declara el grafo.
- `business-backend`: `/agents` permite **crear, editar, elegir default y
  borrar** perfiles nombrados del sintetizador (nombre + persona +
  modelo). Las herramientas y el rol de cada nodo siguen siendo
  read-only, derivados del catálogo / privilegios.
- `business-backend`: pantalla `/agents/flow` — diagrama + tabla del
  flujo, como `graph_flow/show` del curso. No edita aristas.

### Deliberadamente descartado (con razón)

- **Nodos nuevos desde la UI.** Un agente sin función, sin privilegio y
  sin precondición en el orquestador no corre. El curso tampoco lo
  permitía: `GraphFlow::NODES` es estático.
- **Asignar tools o «skills» libres desde la UI.** Las tools salen de
  `AGENT_PRIVILEGES`; un allowlist editable mentiría si el dispatcher no
  lo aplica. «Skill» en el vocabulario del pedido se mapea al **rol +
  explicación + tools** del catálogo, no a un pack de markdown nuevo.
- **Hacer LLM-driven a los deterministas** para que la persona aplique
  en más nodos: misma razón que `add-agent-profiles` (evals medidos).
- **Avatar.** No cambia ninguna respuesta; Active Storage no existe acá.
- **Editor de aristas / orden del orquestador.** El flujo se *muestra*,
  no se reescribe. Cambiar `_ORDER` o las precondiciones es un change
  de orquestación, no de consola.
- **`reasoning_effort` y knobs de búsqueda del curso.** Ya existen como
  settings / params de request; un knob que el servicio ignora no se
  expone.

## Capabilities

### New Capabilities

(ninguna — extiende capabilities ya propuestas)

### Modified Capabilities

- `agent-profiles`: varios perfiles nombrados por agente configurable,
  con default; la topología del grafo viaja con el catálogo.
- `web-console`: alta/edición de perfiles nombrados y pantalla de flujo.
- `answer-orchestration`: una corrida puede elegir el perfil del
  sintetizador; ausente = default.

## Impact

- `ai-service/app/domain/profiles.py` — modelo, repo, resolución por id
  o default
- `ai-service/alembic/versions/` — migración de PK `agent_key` → id +
  `name` + `is_default`
- `ai-service/app/api/config.py` — CRUD de perfiles + topología en GET
- `ai-service/app/api/answer.py`, `answer_agentic.py` — `profile_id`
- `ai-service/app/generation/rag/schemas.py` — campo opcional
- `ai-service/app/domain/graph/catalog.py` — aristas / orden exportables
- `ai-service/app/domain/graph/build.py`, `orchestrator.py` — fuente de
  la topología (sin cambiar el enrutamiento)
- `ai-service/tests/domain/test_profiles.py`,
  `tests/api/test_config_router.py`, `tests/domain/graph/test_catalog.py`,
  `tests/api/test_answer_router.py`, `tests/api/test_answer_agentic_router.py`
- `business-backend/app/agents/` — formularios de perfil nombrado
- `business-backend/app/agents/flow/` — pantalla de flujo (nueva)
- `business-backend/app/api/config/agents/` — proxies del CRUD
- `business-backend/lib/ai-service/{types,config,answer}.ts`
- `business-backend/lib/console-nav.ts`
- `openspec/changes/add-named-agent-profiles-and-flow/specs/`

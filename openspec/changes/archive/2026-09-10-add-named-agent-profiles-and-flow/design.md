## El pedido, traducido al diseño que ya tenemos

El master enseña dos cosas distintas que la UI mezcla en «agentes»:

| En el curso | Qué es realmente | Qué hacemos acá |
|---|---|---|
| `Agents::Profile` (new/edit) | Un **preset nombrado** del agente hecho a mano | Varios perfiles por agente *configurable* |
| `Agents::GraphFlow::NODES` | Un **catálogo didáctico** del grafo, estático | La misma idea, pero servida por `GET /config` |
| Tools / «skills» | Implícitas en cada nodo; no se editan | Rol + explicación + `AGENT_PRIVILEGES` |

«Crear un agente» en esa consola **nunca creó un nodo**. Creó un perfil
(`Exhaustivo`, `Conservador`) que se preselecciona al lanzar. «Armar el
flujo» era *verlo*, no reescribirlo. Copiar la UX sin copiar esa
distinción sería un editor de grafo que el dispatcher no honra.

## Por qué no un editor de grafo

Tres razones, y cualquiera alcanza:

1. **Un setting que no hace nada es un defecto.** `add-agent-profiles`
   ya rechaza persistir persona en un agente determinista. Un nodo
   creado desde la UI sin función, sin privilegio y sin `_inputs_ready`
   sería lo mismo a escala de grafo.
2. **El catálogo no se declara dos veces.** El curso escribe
   `GraphFlow::NODES` en Rails *y* el grafo en Python; este repo lo
   evitó a propósito (`catalog.py` + `GET /config`). Un editor en
   Next.js sería la tercera copia.
3. **Los evals miden un grafo fijo.** Cambiar `_ORDER` o meter un LLM
   en `query_planner` desde la consola vuelve incomparables los números
   de `evals/`. Eso es un change de orquestación, con medición, no un
   formulario.

La topología se **expone** (nodos, `kind`, aristas, escalera) para que
la pantalla de flujo no la invente. No se **escribe**.

## Modelo de datos

Hoy `agent_profiles.agent_key` es PK: a lo sumo una fila, anónima. Pasa
a:

```
named_agent_profiles
  id            uuid / serial   PK
  agent_key     text            FK lógica al catálogo (no a una tabla)
  name          text            único por (agent_key, lower(name))
  is_default    bool
  persona       text null
  provider      text null
  model         text null
  temperature   float null
  max_tokens    int null
  updated_at    timestamptz
```

Restricciones de aplicación (el motor no conoce el catálogo):

- `agent_key` ∈ `configurable_agent_keys()` — hoy solo
  `answer_synthesizer`.
- A lo sumo un `is_default` por `agent_key`. Borrar el default promociona
  otro o deja al agente en defaults del servicio.
- Knobs nulos = «usar Settings», igual que `config_payload` del curso.

Migración: la fila actual, si existe, se copia a un perfil
`is_default=true` con `name` `"Default"`. Sin fila, no se inventa
ninguna: el sintetizador sigue cayendo a Settings.

No se agrega tabla nueva de «skills». El vocabulario del pedido se
cubre así:

- **nombre** → `name`
- **personalidad** → `persona` (después de las reglas de grounding)
- **herramientas** → `tools` derivado de `AGENT_PRIVILEGES`
- **skills** → `role` + `explanation` del `AgentSpec`

## Resolución en una corrida

`synthesizer_runtime` sigue siendo el único seam de los tres caminos
(`POST /answer`, `POST /answer/agentic`, runner). Cambia el *cuál*:

1. Si el request trae `profile_id`, se carga esa fila y se verifica
   `agent_key == answer_synthesizer`. Si no, 422.
2. Si no trae id, se carga el default de ese agente.
3. Si no hay default, se resuelve como hoy (todo Settings).

El grafo no lee la base: recibe `llm` + `persona` por config. Un perfil
nuevo no exige redeploy del grafo.

## Topología en `GET /config`

Hoy el catálogo describe nodos. Le falta lo que el diagrama necesita
para no hardcodear conectores:

- `edges`: de cada nodo, a quién puede ir (`orchestrator` → especialistas
  + gate; cada especialista → `orchestrator`; gate → `END`). Sale de
  `build.py`, no de prosa.
- `ladder`: el `_ORDER` del orquestador, para que la tabla didáctica
  muestre la escalera de fallback.

Un test de drift compara esas listas con el grafo compilado y con
`_ORDER`. Si se agrega un nodo en código y no en el catálogo, falla el
suite — el mismo contrato que ya tiene `test_catalog.py`.

## Alternativas que perdieron

- **Dejar la fila anónima y solo agregar la pantalla de flujo.** Cubre
  «ver el flujo» y no «crear un agente». El pedido era las dos cosas.
- **Perfiles en `business-backend` (como el curso).** El filesystem de
  Railway es efímero y el browser no habla con el servicio; un preset
  que no viaja al seam de síntesis no tiene efecto. Por eso los
  perfiles ya viven en Postgres del `ai-service`.
- **Skills como markdown libre por perfil.** Es un segundo system
  prompt. La persona ya es ese gancho, y está subordinada a las reglas.
  Un pack extra sin medición duplica el knob y complica el eval.
- **Avatar + Active Storage.** Cero efecto en la respuesta; dependencia
  nueva sin `proposal` que la justifique más allá de cosmética.

## Cómo se agrega un nodo de verdad (fuera de este change)

Sigue siendo el camino de código que ya existe: función del agente →
`AGENT_PRIVILEGES` → `AgentSpec` → `AGENT_NODES` + `_ORDER` +
`_inputs_ready`. Este change no lo acorta ni lo esconde: la pantalla de
flujo *mostrará* el nodo nuevo en cuanto el servicio lo sirva.

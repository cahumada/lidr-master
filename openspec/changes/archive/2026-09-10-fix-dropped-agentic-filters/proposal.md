## Why

`POST /answer/agentic` y `POST /answer/agentic/start` aceptan `module_code` y
`window_type_name` en su body y **los descartan**.

`initial_state()` ([runner.py:85](../../../ai-service/app/domain/graph/runner.py))
copia al estado `limit`, `max_per_document`, `lexical`, `split` y `rerank`, y no
siembra ninguna clave `filters`. El `evidence_retriever` arma sus
`SearchFilters` desde `state["filters"]`, que solo escribe el `query_planner` a
partir de dos fuentes: los códigos con forma de transacción que encuentra en el
texto de la pregunta, y los anchors de la sesión. El filtro que el cliente mandó
no participa en ninguna de las dos.

Tres cosas lo vuelven un defecto y no una omisión menor:

1. **El mismo contrato se comporta distinto según el endpoint.** `POST /answer`
   sí los honra ([answer.py:70](../../../ai-service/app/api/answer.py)). Los dos
   reciben `AnswerRequest`; uno filtra y el otro no.
2. **La consola los manda por el camino que los ignora.** `answer-console.tsx`
   los envía a `/answer/agentic/start`, así que los selectores de módulo y de
   tipo de ventana de la pantalla de respuesta **no hacen nada**. El operador
   elige `CA`, la búsqueda no se recorta, y nada se lo dice.
3. **Es exactamente el patrón que el repo prohíbe con nombre y apellido.** La
   spec de `conversation-memory` lo dice sobre `session_id` en `/answer`:
   *"aceptar un campo e ignorarlo es el comportamiento silencioso que este
   servicio no permite"*. Lo que ahí se resolvió con un 422, acá está pasando
   en silencio.

Encontrado el 2026-09-10 mientras se armaba el smoke de pausa/resume: un filtro
`module_code=["ZZZ"]` no produjo cero hits, que es lo que lo destapó.

## What Changes

- `initial_state()` siembra `filters` en el estado con `module_code` y
  `window_type_name` del request, marcados como de origen `request`.
- El `query_planner` deja de ser el único autor de `state["filters"]`: resuelve
  la **precedencia** entre las tres fuentes en un solo lugar y anota de dónde
  salió cada valor.
- **Precedencia: request → pregunta → anchor.** Extiende la regla que
  `_apply_anchors` ya documenta —*"el anchor es un default, no una jaula"*— sin
  invertirla: lo que el cliente eligió para este turno gana sobre el código que
  la heurística sacó del texto, que sigue ganando sobre el filtro fijado.
- **Lo que se aplica se reporta.** La respuesta declara los filtros efectivos y
  su origen, como los perfiles ya declaran `profile` / `settings`. La spec de
  `conversation-memory` es explícita: *"un filtro aplicado sin decirlo es un
  defecto, no una comodidad"*.
- La contribución del planner en `agent_contributions` nombra la fuente de cada
  filtro, no solo el valor.

Fuera de alcance:

- **Rechazar los campos con 422.** Es la otra salida posible y la descarto en
  `design.md`: la consola tiene los controles construidos y el usuario espera
  que recorten.
- **El filtro por `window_status`.** Sigue fuera de alcance donde ya estaba.

## Capabilities

### Modified Capabilities

- `answer-orchestration`: los filtros del request entran al estado del grafo, la
  precedencia entre las tres fuentes queda declarada, y los filtros efectivos se
  reportan con su origen.

## Impact

- `ai-service/app/domain/graph/runner.py` — `initial_state()` siembra `filters`.
- `ai-service/app/domain/graph/agents/query_planner.py` — la resolución de
  precedencia y el registro de la fuente.
- `ai-service/app/generation/rag/schemas.py` — los filtros efectivos y su origen
  en la respuesta agéntica.
- `ai-service/app/api/answer_agentic.py` — que viajen en los tres payloads
  (completado, pausado, progreso).
- `ai-service/tests/domain/graph/` y `tests/api/` — tests.
- La consola no necesita cambios para que sus selectores empiecen a funcionar;
  mostrar los filtros efectivos sí sería un change de `web`.

## Verificado (2026-09-10)

La reproducción original, contra el servicio local, por `POST /answer/agentic`:

| | antes | después |
|---|---:|---:|
| `module_code=["ZZZ"]` + pregunta cualquiera | **5 citas** | **0 citas** |

Después del cambio la respuesta además declara
`effective_filters: [{"field": "module_code", "values": ["ZZZ"], "source": "request"}]`,
y el gate pausa correctamente por falta de evidencia.

**Paridad entre endpoints**, con `module_code=["DMECAR"]` y la misma pregunta:
los dos devuelven 6 citas y todas del módulo `DMECAR`. Los `document_id` no
coinciden y no deberían: el camino agéntico descompone la pregunta e intercala
los hits de cada subconsulta.

**La consola no necesita cambios** para que sus selectores empiecen a recortar.
Mostrar los filtros efectivos y su origen en la pantalla sí sería un change de
`web`.

## Lo que este change destapó, y NO arregla

Hacer visibles los filtros efectivos dejó ver un defecto **más grave que el que
este change corrige**, y en la otra fuente:

`_suggest_filters` deriva el filtro de módulo del prefijo de un código de
transacción —`CA014` → `module_code=["CA"]`— pero los `module_code` que el
corpus realmente tiene son los códigos del nodo módulo del árbol `WINDOWS`:
`DMECAR`, `DMECLI`, `DMECOB`… **Los 17 valores reales no incluyen ninguno de
dos letras.** La heurística produce un vocabulario que no matchea nada.

Medido contra el servicio local:

| pregunta | filtro efectivo | citas |
|---|---|---:|
| `¿Qué valida CA014?` | `module_code=["CA"]` (`question`) | **0** |
| `¿Qué valida el tratamiento de pólizas?` | ninguno | 5 |

Es decir: **en el camino agéntico, nombrar una transacción —la forma más natural
de preguntar— recupera cero evidencia.** El motor contesta que no hay
información suficiente sobre un documento que tiene en el corpus.

La distinción que sugiere el arreglo: un filtro **explícito** que no matchea
nada DEBE devolver cero, porque alguien lo pidió; un filtro **heurístico** que
no matchea nada debe descartarse y registrarse, porque nadie lo pidió. Hoy los
dos se aplican igual.

No se arregla acá: sale a su propio change, porque decidir entre mapear el
prefijo al módulo real, validar el valor antes de aplicarlo, o quitar la
heurística —el camino de coincidencia exacta ya encuentra `CA014` por
`document_id`— es una decisión de diseño y no un ajuste.

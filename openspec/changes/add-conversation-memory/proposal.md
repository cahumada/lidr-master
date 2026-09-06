## Why

La consola de `/answer` **parece** un chat: acumula turnos, los apila en
pantalla, muestra la pregunta de cada uno arriba de su respuesta. El backend
no tiene nada de eso. El payload que sale de `ask()` en
`business-backend/app/answer/answer-console.tsx` lleva `question` y los
knobs de recuperación, nada más; `AnswerAgentState`
(`app/domain/schemas.py`) no tiene un campo de mensajes; y
`OpenAICompatibleChatLLM.complete()` arma literalmente
`[system, user]` en cada llamada. Cada `POST /answer/agentic/start` crea un
`thread_id` nuevo con `uuid4()`.

La brecha entre lo que la pantalla promete y lo que el servicio hace es el
defecto. Una pregunta de seguimiento —«¿y para siniestros?», «¿eso también
vale para CA014?», «mostrame el efecto de esa misma transacción»— llega al
`query_planner` como texto suelto sin referente. No falla ruidosamente:
`decompose` la parte, el retriever busca «y para siniestros» contra el
corpus, trae los chunks que más se le parezcan, y el sintetizador redacta
con aplomo una respuesta bien citada **a una pregunta que nadie hizo**. En
un corpus de reglas de negocio de seguros, una respuesta citada a la
pregunta equivocada es peor que un error: viene con procedencia verificable
adosada.

Esta es la diferencia de fondo con el proyecto de referencia del curso
([`agents_event`](https://github.com/LIDR-academy/ai-engineering/tree/agents_event/ai-service/app/generation/conversation)),
y define qué se porta y qué no. Ahí la memoria alimenta la **generación**:
un estimador conversacional donde el modelo tiene que recordar que el NDA
está firmado y que el scope se congeló. Acá el problema aparece antes, en la
**recuperación**: si la pregunta no se resuelve contra lo que ya se dijo, el
retriever busca lo que no es y ninguna cantidad de memoria en el prompt de
síntesis lo arregla — el sintetizador solo puede citar lo que le trajeron.

De ahí la forma de este change: memoria de **hechos resueltos** que entra al
planner, y no un historial de prosa que entra al sintetizador. Los cuatro
mecanismos del curso se adaptan, no se copian; `design.md` dice cuál sí,
cuál con cambios, y cuál queda afuera con su condición para volver.

**Depende de dos changes en curso.** `add-answer-context-budget` define el
presupuesto de contexto dentro del cual se recorta la memoria; sin él, la
memoria sería tokens que nadie cuenta y este change reintroduciría el
problema que aquél cierra. `reorganize-console-modules` ya declara la
pantalla como un hilo de turnos —hoy respaldado solo por el estado del
browser—, y este change es el que lo respalda en el servicio.

## What Changes

- Capability nueva `conversation-memory` con su propio módulo,
  `app/generation/conversation/`. No cuelga de `rag/`: es memoria de la
  conversación, no una etapa del pipeline de recuperación.
- **Sesión explícita.** `POST /answer/session` devuelve un `session_id`
  emitido por el servicio. `POST /answer/agentic[/start]` acepta
  `session_id` **opcional**: sin él, el comportamiento actual queda intacto
  —una pregunta, sin memoria, prompt `v1` byte a byte— y ninguna integración
  existente se rompe. `session_id` NO es `thread_id`: un thread es una corrida
  del grafo, una sesión son muchas.
  `POST /answer` —el camino de un solo tiro, el que llama el eval— **rechaza**
  un `session_id` con 422 en vez de aceptarlo e ignorarlo: no tiene planner
  que resuelva la pregunta antes de recuperar, y aceptar un campo para no
  usarlo respondería sin memoria mientras quien llama cree lo contrario.
- **Hechos de sesión** (`ConversationFacts`), el análogo de la
  `ProjectMetadata` del curso: filtros activos (`module_code`,
  `window_type_name`), códigos de transacción mencionados, y los
  `document_id` citados en la última respuesta. Se **re-renderizan en el
  system prompt en cada turno** en vez de guardarse como mensajes, que es lo
  que hace que sobrevivan a cualquier recorte de la ventana.
- **Resolución de referencias en el planner.** `query_planner` resuelve la
  pregunta contra los hechos de la sesión **antes** de descomponer, y deja
  la pregunta resuelta en el estado junto a la original. El retriever busca
  la resuelta; la respuesta muestra las dos. Esta es la pieza que el curso
  no necesita y acá es el motivo del change.
- **Ventana deslizante** de los últimos `CONVERSATION_MAX_TURNS = 4` pares
  (pregunta, respuesta), con la respuesta guardada recortada. Alimenta solo
  al sintetizador, para que sepa qué se contestó y no repita. Subordinada a
  la evidencia: ver el presupuesto, abajo.
- **Anchors** adaptados al dominio: no NDAs ni budgets congelados, sino
  restricciones que el usuario fija explícitamente («de acá en adelante solo
  módulo CA»). Detector heurístico, sin llamada LLM. Un anchor no se
  desaloja de la ventana y se aplica como filtro por default en los turnos
  siguientes — visible en la respuesta, nunca en silencio.
- **Presupuesto propio.** `CONVERSATION_MEMORY_MAX_TOKENS = 1024`, recortado
  **dentro** del presupuesto de contexto que define
  `add-answer-context-budget`, no encima. La evidencia gana: si la memoria
  no entra, se recorta la memoria, jamás los chunks. El orden es deliberado
  y es lo contrario de lo que haría un chat genérico.
- **El guardrail de citas no se afloja.** `citation_validator` sigue
  validando contra los hits de **este** turno. Un `document_id` citado en un
  turno anterior no respalda nada en el actual.
- Persistencia en Postgres (tabla `conversation_sessions` + migración
  alembic), no en memoria del proceso. Justificado en `design.md`.
- La consola manda `session_id`, muestra la pregunta resuelta cuando difiere
  de la escrita, y ofrece «empezar de nuevo» —que descarta la sesión— como
  acción visible.

**Deliberadamente afuera (no de este change):**

- **Resumen acumulativo.** Es el mecanismo del curso que más cuesta (una
  llamada LLM por compactación) y el que menos aporta acá: con hechos
  estructurados y preguntas resueltas, cuatro pares de ventana alcanzan.
  Condición para volver: si aparecen sesiones donde la ventana se llena y
  el `resolver` pierde referentes que estaban a más de cuatro turnos,
  entonces sí — y con esa evidencia adelante, no antes.
- **Detector de anchors por LLM.** El curso lo tiene como opt-in
  (`ANCHOR_DETECTION_MODE`). Acá el conjunto de anchors es chico y explícito
  (el usuario fija un filtro), así que la heurística es suficiente y el
  clasificador sería una llamada por turno para decidir algo que el usuario
  ya dijo con todas las letras.
- **Memoria entre sesiones o entre usuarios.** No hay usuarios en el
  servicio; inventarlos para esto sería un change distinto.
- **Streaming de la respuesta.** Sigue afuera, como en
  `add-answer-live-progress`.

## Capabilities

### New Capabilities
- `conversation-memory`: sesiones de conversación con hechos estructurados,
  resolución de preguntas referenciales, ventana deslizante de turnos y
  anchors de filtros, con presupuesto propio subordinado a la evidencia.

### Modified Capabilities
- `answer-orchestration`: el estado del grafo transporta la sesión, el
  planner resuelve la pregunta antes de descomponer, y la sesión se
  actualiza al cerrar el turno.
- `web-console`: la pantalla de respuesta pasa a ser una conversación real
  —manda `session_id`, muestra la pregunta resuelta, permite reiniciar.

## Impact

- `ai-service/app/generation/conversation/__init__.py` (nuevo)
- `ai-service/app/generation/conversation/models.py` — `ConversationFacts`,
  `Turn`, `ConversationSession`.
- `ai-service/app/generation/conversation/store.py` — persistencia Postgres.
- `ai-service/app/generation/conversation/facts.py` — extracción y merge de
  hechos (escalares pisan, listas unen).
- `ai-service/app/generation/conversation/resolver.py` — resolución de
  preguntas referenciales.
- `ai-service/app/generation/conversation/anchors.py` — detector heurístico
  de filtros fijados.
- `ai-service/app/generation/conversation/budget.py` — recorte de la memoria
  dentro del presupuesto de contexto.
- `ai-service/app/domain/graph/agents/query_planner.py` — resuelve antes de
  descomponer.
- `ai-service/app/domain/graph/agents/answer_synthesizer.py` — bloque de
  memoria en el prompt.
- `ai-service/app/domain/schemas.py` — `AnswerAgentState` lleva sesión,
  pregunta resuelta y hechos.
- `ai-service/app/api/answer_agentic.py` — `session_id` opcional; la
  respuesta expone `resolved_question` y los hechos vigentes.
- `ai-service/app/api/answer_session.py` (nuevo) — `POST /answer/session`,
  `GET /answer/session/{id}`, `DELETE /answer/session/{id}`.
- `ai-service/app/foundation/prompts/answer/v2/{system,user}.j2` — bloque de
  memoria. Versión nueva, no se pisa `v1`.
- `ai-service/alembic/versions/*_conversation_sessions.py` (nueva tabla)
- `ai-service/app/config.py` — `CONVERSATION_MAX_TURNS`,
  `CONVERSATION_MEMORY_MAX_TOKENS`, `CONVERSATION_SESSION_TTL_DAYS`.
- `ai-service/.env.example` — documenta los knobs nuevos.
- `ai-service/tests/generation/conversation/` (nuevo)
- `ai-service/tests/domain/graph/agents/test_query_planner.py`
- `ai-service/tests/api/test_answer_session_router.py` (nuevo)
- `business-backend/lib/ai-service/types.ts` — sesión en el contrato.
- `business-backend/app/api/answer/session/route.ts` (nuevo)
- `business-backend/app/answer/answer-console.tsx` — sesión, pregunta
  resuelta, reinicio.
- `ai-service/README.md` y `openspec/project.md` — la memoria deja de ser un
  hueco declarado.
- `openspec/changes/add-conversation-memory/specs/{conversation-memory,answer-orchestration,web-console}/spec.md`
  — deltas; no se promocionan a `openspec/specs/` hasta archivar.

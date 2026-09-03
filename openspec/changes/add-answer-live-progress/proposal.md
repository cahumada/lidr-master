## Why

`POST /answer/agentic` (de `add-answer-orchestration`) es una sola llamada
bloqueante: el cliente no ve nada mientras el grafo corre — cuatro agentes,
posiblemente una llamada al LLM, retrieval y validación — y recién sabe algo
cuando la respuesta HTTP vuelve. Para una demo del "RAG con agentes" que pide
la rúbrica del proyecto final, eso es una pantalla en blanco seguida de un
resultado, no evidencia de que hay agentes trabajando.

El curso resuelve exactamente esto en la rama `agents_event`
(LIDR-academy/ai-engineering): un buffer de actividad (`GraphActivityLog`)
alimentado por `graph.astream(..., stream_mode="updates")`, traducido a
líneas legibles por `describe_node()`, expuesto por un endpoint de polling y
consumido por un panel que anima cada agente como idle/running/done. A pesar
del nombre de la rama, no es streaming real (SSE/WS) — es polling cada
~1.2-1.5s, y así se replica acá.

**Depende de `add-answer-orchestration` mergeado.** No reimplementa agentes,
grafo, gate ni privilegios — solo agrega una forma de ejecutar el mismo grafo
en background y narrar su avance.

## What Changes

- `ai-service`: nuevo `GraphActivityLog` (buffer en memoria por `thread_id`,
  sin Redis — un solo proceso alcanza; Redis es la variante del curso para
  despliegues multi-worker que este servicio no tiene) y `describe_node()`
  (función pura que traduce el update crudo de cada nodo, incluido
  `__interrupt__`, a una línea legible; nunca lanza).
- `ai-service`: `POST /answer/agentic/start` agenda el grafo en background
  (`asyncio.create_task`, con referencia fuerte para que no lo recolecte el
  GC) y devuelve `202` con un `thread_id` al instante.
- `ai-service`: `GET /answer/agentic/{thread_id}/progress` devuelve la
  actividad narrada hasta ahora y, cuando el estado deja `running`, el
  resultado (completado, pausado para revisión humana, o fallado).
- `ai-service`: `POST /answer/agentic` (el endpoint síncrono existente) NO
  cambia — sigue devolviendo 200/202 en una sola llamada, para quien no
  necesita la vista en vivo. `POST /answer/agentic/resume` gana un efecto
  colateral: si el hilo tiene un buffer de actividad (vino de `/start`),
  anota la decisión humana ahí para que un poll posterior narre el cierre.
- `business-backend`: la pantalla `/answer` pasa de "enviar y esperar" a
  "iniciar y sondear" — un panel "Flujo en vivo" anima los cuatro agentes más
  el gate como idle/running/done con el último mensaje de cada uno, usando el
  mismo orden de dependencia que la escalera de fallback del orquestador.

### Deliberadamente descartado (con razón)

- **Streaming real (SSE/WebSockets)**: el curso tampoco lo tiene pese al
  nombre de la rama. Polling cada 1.2s es suficiente para una corrida de
  segundos y no agrega infraestructura (conexiones persistentes, proxies que
  las corten) por una ganancia perceptual mínima.
- **Redis para el activity log**: un dict de un proceso alcanza mientras el
  servicio corra como una sola instancia (Railway, hoy). El día que haya más
  de un worker, ESA es la señal para cambiarlo.
- **Perfiles de agente editables por UI** (persona/avatar/modelo por agente,
  del curso): personalización de producto sin relación con ningún gap de la
  rúbrica; no se construye ahora.

## Capabilities

### Modified Capabilities

- `answer-orchestration`: agrega una vía de ejecución en background con
  progreso narrado, además de la síncrona existente.

## Impact

- `ai-service/app/domain/graph/activity.py` (nuevo)
- `ai-service/app/domain/graph/runner.py` (nuevo)
- `ai-service/app/dependencies.py` — `get_activity_log()`
- `ai-service/app/api/answer_agentic.py` — `/start`, `/{thread_id}/progress`,
  efecto colateral en `/resume`
- `ai-service/tests/domain/graph/test_activity.py` (nuevo)
- `ai-service/tests/api/test_answer_agentic_progress_router.py` (nuevo)
- `business-backend/lib/ai-service/types.ts` — `GraphActivityEntry`,
  `AnswerAgenticStart`, `AnswerAgenticProgress`
- `business-backend/lib/ai-service/answer.ts` — `answerAgenticStart`,
  `answerAgenticProgress`
- `business-backend/app/api/answer/agentic/start/route.ts` (nuevo)
- `business-backend/app/api/answer/agentic/[threadId]/progress/route.ts` (nuevo)
- `business-backend/app/answer/answer-console.tsx` — panel "Flujo en vivo"
- `openspec/changes/add-answer-live-progress/specs/answer-orchestration/spec.md`

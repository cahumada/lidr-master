# Implementation Tasks

## 1. OpenSpec

- [x] 1.1 `proposal.md` con dependencia de `add-answer-orchestration` y lo
      deliberadamente descartado (streaming real, Redis, perfiles de agente).
- [x] 1.2 Delta `specs/answer-orchestration/spec.md`.

## 2. Activity log

- [x] 2.1 `app/domain/graph/activity.py`: `describe_node()` puro y sin
      excepciones (incluye `__interrupt__`), `GraphActivityLog` en memoria
      por `thread_id` (start/append/finish/read).
- [x] 2.2 `get_activity_log()` singleton en `dependencies.py`.

## 3. Ejecución en background

- [x] 3.1 `app/domain/graph/runner.py`: `thread_config`/`initial_state`
      (movidos desde `answer_agentic.py`, reusados por el endpoint síncrono
      sin cambiar su comportamiento), `run_agentic_background` vía
      `graph.astream(..., stream_mode="updates")` con sesión propia
      (`get_async_session_factory()`, no la del request).
- [x] 3.2 `POST /answer/agentic/start`: agenda la tarea, guarda una
      referencia fuerte (`_BACKGROUND_RUNS`) para que asyncio no la recolecte
      a mitad de camino, devuelve `202` + `thread_id` al instante.
- [x] 3.3 `GET /answer/agentic/{thread_id}/progress`: `404` si el
      `thread_id` no existe; mientras corre, devuelve solo `activity`; al
      terminar, agrega el resultado (completado/pausado/fallado).
- [x] 3.4 `POST /answer/agentic/resume`: si el hilo tiene buffer de
      actividad, anota la decisión humana y cierra el buffer como
      `completed` — best-effort, no rompe el camino síncrono que nunca tuvo
      buffer.

## 4. Tests

- [x] 4.1 `tests/domain/graph/test_activity.py`: `describe_node` por cada
      nodo + `__interrupt__` + forma desconocida degradando sin lanzar;
      `GraphActivityLog` start/append/finish/read.
- [x] 4.2 `tests/api/test_answer_agentic_progress_router.py`: `/start` (202
      + thread_id), `/progress` narrando actividad hasta completar, hasta
      pausa humana, `404` con thread_id desconocido, y falla registrada.
- [x] 4.3 `tests/api/test_answer_agentic_router.py` sigue en verde sin
      tocarse (el endpoint síncrono no cambió de comportamiento).

## 5. Consola web

- [x] 5.1 Tipos `GraphActivityEntry`, `AnswerAgenticStart`,
      `AnswerAgenticProgress` en `types.ts`.
- [x] 5.2 `answerAgenticStart` / `answerAgenticProgress` en `answer.ts`.
- [x] 5.3 Route Handlers `POST /api/answer/agentic/start`,
      `GET /api/answer/agentic/[threadId]/progress`.
- [x] 5.4 `answer-console.tsx`: `ask()` pasa a iniciar + sondear
      (`POLL_INTERVAL_MS`, con cleanup del timeout al desmontar); panel
      `LiveFlowPanel` con los cuatro agentes + gate como
      idle/running/done, usando el mismo orden de dependencia que la
      escalera de fallback del orquestador.

## 6. Documentación

- [x] 6.1 `ai-service/README.md`: variante de progreso en vivo en la sección
      "Agentes y orquestación".
- [x] 6.2 `business-backend/README.md`: panel "Flujo en vivo" en la
      pantalla `/answer`.

## 7. Verificación

- [x] 7.1 `uv run pytest` y `uv run ruff check .` en verde desde
      `ai-service/` (564 passed sin integración; 569 con Postgres real).
- [x] 7.2 `pnpm lint` y `pnpm build` en verde desde `business-backend/`.
- [x] 7.3 `python scripts/validate_specs.py` en verde desde la raíz.
- [x] 7.4 Smoke real de punta a punta contra la app corriendo en el browser
      (Postgres + pgvector local, OpenAI real): pregunta sin evidencia en el
      corpus cargado → el flujo en vivo narra los cuatro agentes → pausa
      202 con motivos reales (confianza 0.10, sin evidencia) → aprobar →
      respuesta final con traza de enrutado completa.
- [ ] 7.5 No archivar hasta que `add-answer-orchestration` esté archivado
      (depende de ese smoke de pausa/resume manual, todavía pendiente ahí).

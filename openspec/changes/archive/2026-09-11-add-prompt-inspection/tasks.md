# Implementation Tasks

Todo en `add-dependency-table-anchoring-ai-service`: PR único, decisión del dueño
(2026-09-11), porque hay otra sesión tocando `answer-console.tsx` y dos ramas se
pisarían ahí.

## 1. Persistencia

- [x] 1.1 `AnswerPromptRow` en `ai-service/app/foundation/persistence/prompts.py`:
      `id` (uuid), `tenant_id`, `created_at`, `agent`, `model`, `profile_id`,
      `context_budget`, `system_text`, `user_text`, `thread_id`, `session_id`.
      Índice por `(tenant_id, created_at)` — es por donde barre la retención.
- [x] 1.2 Migración Alembic. No reformatear `alembic/versions/`.
- [x] 1.3 `save_prompt()`: inserta y barre en la misma transacción las filas del
      tenant anteriores a la ventana. Nunca propaga una excepción al camino de
      respuesta: si falla, se loguea y se sigue sin `prompt_id`.
- [x] 1.4 `read_prompt()` por id, con el mismo filtro de ventana que el barrido —
      una fila que sobrevivió a un barrido que no corrió igual está vencida.
- [x] 1.5 `ANSWER_PROMPT_RETENTION_DAYS` (default 7) en `app/config.py` y
      `ai-service/.env.example`.

## 2. Guardar al enviar

- [x] 2.1 `app/generation/rag/answer.py`: guardar junto a `llm.complete()`.
- [x] 2.2 `app/domain/graph/agents/answer_synthesizer.py`: ídem, con el
      `thread_id` y el `session_id` que ya viajan en el estado.
- [x] 2.3 Los dos guardan el `system` y el `user` **exactos** que recibió el
      modelo — no un re-render ni una copia recortada.

## 3. Contrato

- [x] 3.1 `prompt_id` en `AnswerResponse` (`app/generation/rag/schemas.py`) y en
      los tres shapes de `app/api/answer_agentic.py` (completed, paused,
      progress). `Field(description=...)` bilingüe.
- [x] 3.2 `GET /answer/prompts/{prompt_id}` en `app/api/answer.py`: router
      delgado, 404 cuando no está o venció. `AnswerPromptResponse` Pydantic.
- [x] 3.3 Tests de contrato en `tests/api/`: el payload lleva el id y NO el
      texto; el endpoint devuelve las dos partes; 404 para id inexistente.

## 4. Tests del servicio

- [x] 4.1 `tests/foundation/persistence/test_prompts.py`: el barrido borra lo
      vencido, no toca otros tenants, y una lectura vencida no devuelve nada.
- [x] 4.2 Test de que una escritura fallida no rompe la respuesta.
- [x] 4.3 Test de que `llm_usage_events` no cambia de forma.
- [x] 4.4 `pytest` y `ruff check .` en verde.

## 5. El gate de rol para route handlers

- [x] 5.1 `business-backend/lib/auth/api-guards.ts`: `requireAdmin()` que
      resuelve con `auth()` y devuelve un `Response` 403 —o `null` si pasa—,
      usando `asRole` para que un rol desconocido caiga al menos privilegiado.
- [x] 5.2 Tests en `lib/auth/` con el runner que ya usa el proyecto
      (`node --test`), sobre la decisión pura: admin pasa, usuario no, rol
      desconocido no, sin sesión no.
- [x] 5.3 **No** aplicarlo a las rutas `/api` existentes en este change. Dejar
      anotado en el proposal que `/api/usage/*`, `/api/agents/*`, `/api/corpus/*`
      y `/api/users/*` sirven datos de pantallas admin sin chequear rol.

## 6. Consola

- [x] 6.1 `prompt_id` en `lib/ai-service/types.ts` (los tres shapes) y
      `AnswerPromptView`.
- [x] 6.2 `app/api/answer/prompts/[promptId]/route.ts`: `requireAdmin()` primero,
      recién después el relay al servicio.
- [x] 6.3 `app/(console)/answer/prompt-modal.tsx`: pide al abrir, muestra
      `system` y `user` preformateados y rotulados, dice cuándo el prompt venció.
- [x] 6.4 `answer-console.tsx`: el link en el turno, sólo si hay `prompt_id` y el
      rol es `administrador`. El rol llega por prop desde el server component —
      la pantalla ya lo recibe para el sidebar.
- [x] 6.5 `pnpm test`, `eslint` y `pnpm build` en verde.

## 7. Specs

- [x] 7.1 Los deltas reflejan lo implementado; corregirlos si se apartó.
- [x] 7.2 `python scripts/validate_specs.py` sin errores.
- [x] 7.3 `openspec/standards/app-routes.md`: sumados `GET /answer/prompts/{id}`
      y la ruta del BFF, anotando que es el único route handler con gate de rol.

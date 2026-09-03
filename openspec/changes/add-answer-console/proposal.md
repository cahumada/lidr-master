## Why

Fase 2 del servicio (`add-answer-orchestration`) expone `POST /answer/agentic`
y `/resume`, pero la consola web solo cubría búsqueda, ingesta y corpus
(`add-web-console`). Sin pantalla, el flujo agentico sigue siendo Swagger o
`curl` — el mismo hueco que tenía `/search` antes de la consola.

El curso ([session_16_live](https://github.com/LIDR-academy/ai-engineering/tree/session_16_live))
resuelve esto con `supervisor_estimation_runs`: formulario → resultado o pausa
→ bandeja de revisión con razones + traza de enrutamiento + approve/reject.
Esta propuesta replica esa **postura** (no las pantallas Rails ni la persistencia
en Postgres del curso) en Next.js, consumiendo nuestros endpoints de respuesta
agentica.

**Depende de:** `add-answer-generation` y `add-answer-orchestration` en el
servicio IA.

## What Changes

- Cliente `lib/ai-service/answer.ts` + tipos en `types.ts` (espejo 1:1 de
  `AnswerRequest`, `AnswerAgenticResponse`, pausa 202).
- Route Handlers `app/api/answer/agentic` y `.../resume` — relay al servicio,
  incluyendo **202 Accepted** como éxito con cuerpo distinto (no error).
- Pantalla `/answer`: pregunta, mismos knobs medidos que búsqueda, respuesta
  citada, traza de `routing_history`, y panel de revisión humana cuando el
  servicio devuelve 202 (approve / reject + nota opcional).
- Nav + tarjeta en la portada.

**Deliberadamente afuera:**

- Bandeja persistente / inbox en DB (el curso persiste `SupervisorEstimationRun`;
  acá el `thread_id` vive en el estado de la sesión del browser hasta resume).
- Pantalla separada para `POST /answer` lineal (se puede agregar después; el
  foco es el flujo agentico que el curso enseña en sesión 14).

## Capabilities

### New Capabilities
(ninguna — extiende `web-console`)

### Modified Capabilities
- `web-console`: pantalla de respuesta agentica con gate humano visible.

## Impact

- `business-backend/lib/ai-service/types.ts`
- `business-backend/lib/ai-service/base-client.ts`
- `business-backend/lib/ai-service/answer.ts`
- `business-backend/app/api/answer/agentic/route.ts`
- `business-backend/app/api/answer/agentic/resume/route.ts`
- `business-backend/app/answer/page.tsx`
- `business-backend/app/answer/answer-console.tsx`
- `business-backend/app/layout.tsx`
- `business-backend/app/page.tsx`
- `openspec/changes/add-answer-console/specs/web-console/spec.md`

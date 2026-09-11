## Why

Cuando una respuesta sale mal, hoy no hay forma de ver **qué se le mandó al
modelo**. La consola muestra la evidencia recuperada, la memoria aplicada y —
desde `add-dependency-table-anchoring`— el contexto de base, pero cada uno por
separado y ya interpretado. El prompt real, con sus bloques numerados, su
persona, sus guardrails y el orden en que quedaron, no lo ve nadie.

Eso convierte cada diagnóstico en una reconstrucción a mano: mirar tres paneles,
acordarse del orden de ajuste, y suponer cómo quedó el texto. Y suponer es
exactamente lo que falla, porque el orden de ajuste —evidencia → memoria → base—
y los recortes de presupuesto son justamente lo que produce las respuestas malas.

**El prompt no está guardado en ningún lado.** `build_budgeted_messages` devuelve
`system` y `user`, los dos caminos de síntesis se los pasan a `llm.complete()` y
se descartan ahí mismo. No hay nada que mostrar todavía.

Y **no se puede reconstruir después**. El perfil del sintetizador, la persona,
los guardrails, la memoria de la sesión y la corrida activa del mirror cambian
entre una respuesta y el momento de mirarla. Re-renderizar mostraría un prompt
que nunca se envió, presentado como si sí — el mismo defecto que
`business-db-context` evita al fechar la vigencia con la corrida y no con
`now()`.

## What Changes

- **El prompt se guarda cuando se envía, y solo entonces.** Una fila por
  completion de síntesis en `answer_prompts`, escrita en el mismo lugar donde hoy
  se llama al modelo. Lleva el `system` y el `user` **tal como salieron**, más el
  modelo, el perfil y el presupuesto con el que se armaron.
- **La respuesta devuelve un `prompt_id`**, no el prompt. Son ~60 KB por
  respuesta (`ANSWER_MAX_CONTEXT_TOKENS=16384`) con el corpus adentro: meterlo en
  cada payload se lo mandaría por la red a todos, incluido el `usuario` que no
  tiene permiso de verlo.
- **Un endpoint propio lo sirve**, `GET /answer/prompts/{prompt_id}`, que la
  consola pide recién cuando se abre el modal.
- **Ventana de 7 días, y se limpia sola.** Cada escritura borra lo que pasó la
  ventana para ese tenant. Es un barrido acotado e indexado, y no un cron que
  alguien tiene que acordarse de configurar — el modo en que una política de
  retención se incumple es que nadie la programó.
- **El link solo lo ve `administrador`, y el endpoint también lo exige.** El
  prompt lleva la persona y los guardrails —cómo responde el producto— más el
  contenido íntegro del corpus.
- **La autorización viaja al route handler.** Hoy el rol se chequea en
  `app/(console)/(admin)/layout.tsx`, que protege **pantallas por directorio**:
  ninguna ruta de `app/api/` mira el rol. Como `/answer` no es una pantalla de
  administración, ocultar el link no alcanza, y este change trae el primer gate
  de rol del lado servidor para un route handler.
- **Un turno reabierto desde `history` no muestra el link** si su snapshot no
  trae el `prompt_id`, con el mismo criterio que ya rige para el usage: la
  consola no inventa lo que el snapshot no trajo.

Fuera de alcance, con su motivo:

- **Los prompts de los otros agentes** (`query_planner`, `citation_validator`).
  El pedido es el contexto de la respuesta, y esos no lo arman. Cuando haga falta
  auditarlos, la tabla ya tiene el `agent` para distinguirlos.
- **Editar el prompt y reenviarlo.** Es un playground, no una inspección, y
  cambia lo que el endpoint significa.
- **Cerrar el hueco de rol en las rutas `/api` que ya existen.** `/api/usage/*`,
  `/api/agents/*`, `/api/corpus/*` y `/api/users/*` sirven datos de pantallas
  admin sin chequear rol. Es un defecto preexistente y real, pero arreglarlo es
  tocar rutas que este change no trae — va como trabajo propio, con el helper
  que este change deja hecho.

## Capabilities

### New Capabilities

- `prompt-inspection`: qué se guarda de cada prompt de síntesis, por cuánto
  tiempo, y cómo se sirve para poder auditar una respuesta.

### Modified Capabilities

- `web-console`: el turno ofrece ver el contexto completo que se envió, sólo al
  rol `administrador` y con el rechazo en el servidor.

## Impact

- `ai-service/app/foundation/persistence/prompts.py` — nuevo: la fila y su
  escritura con barrido de retención.
- `ai-service/app/generation/rag/answer.py`,
  `ai-service/app/domain/graph/agents/answer_synthesizer.py` — guardar al enviar.
- `ai-service/app/api/answer.py` — el endpoint de lectura.
- `ai-service/app/generation/rag/schemas.py`, `ai-service/app/api/answer_agentic.py` — `prompt_id` en los payloads.
- `ai-service/alembic/versions/` — la tabla.
- `ai-service/app/config.py`, `ai-service/.env.example` — la ventana de retención.
- `business-backend/lib/auth/api-guards.ts` — nuevo: el gate de rol para route handlers.
- `business-backend/app/api/answer/prompts/[promptId]/route.ts` — nuevo.
- `business-backend/app/(console)/answer/prompt-modal.tsx` — nuevo.
- `business-backend/app/(console)/answer/answer-console.tsx`, `business-backend/lib/ai-service/types.ts` — el link y el espejo del contrato.

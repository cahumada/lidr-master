## Why

`add-conversation-memory` hizo que un hilo *en la misma carga* recuerde
hechos, anchors y los últimos cuatro pares. No hizo un historial. Tres
huecos, todos verificados contra el código de `main`:

1. **La ventana *es* el registro.**    `ConversationSession.append_turn()`
   recorta `turns` a `CONVERSATION_MAX_TURNS = 4`.
   `close_turn()` en `app/domain/graph/runner.py` guarda
   `answer[:TURN_ANSWER_MAX_CHARS]` (600 caracteres) y no guarda citas.
   `GET /answer/session/{id}` devuelve exactamente eso. Recargar `/answer`
   y releer la sesión no reconstruye el chat: faltan los turnos viejos, el
   resto de cada respuesta y toda la procedencia.
2. **No hay lista.** `SessionStore` sabe `create`, `get`, `save`, `delete`
   y `purge_expired`. No hay `list`. La consola guarda `sessionId` en
   `useState` (`answer-console.tsx`); un F5 pierde el puntero. Las filas
   siguen en Postgres hasta el TTL, inalcanzables.
3. **El comentario de la consola miente.** Dice que el `session_id` hace
   que «la conversación sobreviva a un reload». El código no persiste el
   id ni rehidrata el hilo. El usuario ve un chat vacío sobre una fila
   que nadie vuelve a pedir.

`add-conversation-memory` lo dejó afuera a propósito: «memoria entre
sesiones o entre usuarios… sería un change distinto». Este es ese change,
del lado del servicio. No es más memoria para el planner: es el
transcript que la consola necesita para listar, reabrir y no perder
citas. La pantalla (sidebar, rehidratación) es
[plan-web](../../commands/plan-web.md), sobre este contrato.

La consola ahora tiene usuarios (`add-console-authentication`). El
servicio no. Atar cada conversación a un usuario es el change de auth
de `ai-service` que ese diseño ya nombró, no este. Acá la lista es del
tenant del despliegue — hoy hay uno, `TENANT_ID` de entorno. `design.md`
dice por qué y qué riesgo nuevo introduce.

## What Changes

- Capability nueva `conversation-history`. Vive en el módulo que ya
  existe (`app/generation/conversation/`), no en una capa nueva. Es el
  cuarto slot de la sesión: `facts`, `anchors`, `turns` (memoria) e
  `history` (transcript).
- **`history` no se recorta.** Cada turno cerrado appendea un
  `HistoryTurn` con la respuesta **entera**, la pregunta escrita, la
  resuelta, un snapshot de citas y `grounded`. El TTL sigue siendo el
  único desalojo. `turns` no cambia: sigue en 4 pares con preview de
  600 caracteres y sigue siendo lo único que entra al prompt `v2`.
- **Snapshot de citas, no el `SearchHit` entero.** `document_id`,
  `document_title`, `section`, `bullet_path`, `content_hash`. Sin
  `text`, `score`, `branches` ni `ranks`: eso es payload de
  recuperación, no el registro de «qué se citó». Perder las citas al
  reabrir sería borrar procedencia en silencio.
- **Título sin LLM.** Sale de la primera pregunta (whitespace colapsado,
  tope `CONVERSATION_TITLE_MAX_CHARS = 80`). `PATCH /answer/session/{id}`
  lo renombra. Un título vacío es 422.
- **`GET /answer/sessions`.** Lista resúmenes (`session_id`, `title`,
  `created_at`, `updated_at`, `turn_count`) ordenados por `updated_at`
  desc. Sin filas vacías (0 turnos de history) y sin vencidas. Paginado
  (`limit` default 50, max 100; `offset`). Es enumerable: cualquiera
  que alcance Railway ve todas las conversaciones del tenant. Hoy el
  servicio ya es público; lo nuevo es que los UUID dejan de ser el
  único secreto. Queda escrito, no disimulado.
- **`GET /answer/session/{id}` se ensancha**, no se parte. Suma `title`,
  `history`, `created_at`, `updated_at`. `turns` / `facts` / `anchors` /
  `max_turns` siguen siendo la memoria. Un cliente viejo que ignore
  campos extra no se rompe.
- **Backfill en la migración.** Las filas actuales copian `turns` →
  `history` y toman título de la primera pregunta. Es lo que hay: como
  mucho 4 previews sin citas. Las conversaciones nuevas quedan
  completas; las viejas, marcadas por la ausencia de citas, no
  inventadas.
- El cierre de turno (`close_turn()` en `runner.py`) escribe los dos
  slots. Un turno que pausa en el gate humano no entra a `history`
  hasta que la corrida cierra — la misma regla que ya tiene la memoria.

**Deliberadamente afuera:**

- **Auth del servicio y `user_id` en la fila.** Lo nombró
  `add-console-authentication` (`design.md` §«Lo que queda sin
  resolver»). Inventar un dueño que el servicio no puede verificar es
  peor que no tenerlo: la consola mandaría un id y cualquiera que
  alcance Railway lo falsificaría.
- **Títulos por LLM, resumen acumulativo, streaming.** Siguen afuera
  por las mismas razones que en `add-conversation-memory`.
- **Pantalla.** Sidebar, «nuevo chat» que no borra el historial,
  rehidratación al recargar: `plan-web`.
- **Golden set multi-turno.** Sigue siendo el ítem 7.6 de
  `add-conversation-memory`, no de este change.

**Sin dependencias nuevas.**

## Capabilities

### New Capabilities
- `conversation-history`: transcript durable de cada conversación
  (respuesta entera + snapshot de citas), título, listado paginado y
  reapertura por id, sin tocar la ventana de memoria ni el resolver.

### Modified Capabilities
- Ninguna. Los requirements de `conversation-memory` (hechos, ventana
  de 4, anchors, presupuesto, resolver) no se mueven. Este change
  extiende la misma fila y el mismo `GET`; no cambia lo que el planner
  lee ni lo que el sintetizador ve.

## Impact

- `ai-service/app/generation/conversation/models.py` — `HistoryTurn`,
  `CitationSnapshot`; `ConversationSession.history` y `title`;
  `append_history()` (no recorta) distinto de `append_turn()`.
- `ai-service/app/generation/conversation/store.py` — columna `history`
  y `title` en `ConversationSessionRow`; `list_recent()`; `rename()`.
- `ai-service/alembic/versions/*_conversation_history.py` — columnas +
  backfill desde `turns`.
- `ai-service/app/domain/graph/runner.py` — al cerrar el turno, append
  del `HistoryTurn` con respuesta entera y snapshot de `citations`.
- `ai-service/app/api/answer_session.py` — `GET /answer/sessions`,
  `PATCH /answer/session/{id}`; `SessionView` gana `title`, `history`,
  timestamps.
- `ai-service/app/config.py` y `ai-service/.env.example` —
  `CONVERSATION_TITLE_MAX_CHARS`.
- `ai-service/tests/generation/conversation/test_models.py` —
  history no se recorta cuando la ventana sí.
- `ai-service/tests/generation/conversation/test_store.py` — listado,
  backfill, rename, exclusiones (vacía / vencida).
- `ai-service/tests/api/test_answer_session_router.py` — contrato del
  listado, del GET ensanchado y del PATCH (200 / 404 / 422).
- `openspec/standards/app-routes.md` — filas nuevas en la tabla del
  servicio IA. Los Route Handlers del BFF los agrega `plan-web`.
- `openspec/changes/add-conversation-history/specs/conversation-history/spec.md`
  — deltas.

La consola y `lib/ai-service/types.ts` no se tocan en esta rama.

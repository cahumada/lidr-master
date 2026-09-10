## Why

El servicio ya sabe listar y reabrir conversaciones
(`add-conversation-history`: `GET /answer/sessions`,
`GET /answer/session/{id}` con `history`, `PATCH` del título). La
consola no. Tres huecos, todos verificados contra
`business-backend/` en `main`:

1. **El hilo vive en `useState`.** `sessionId` y `turns` se pierden
   en un F5. El comentario de `answer-console.tsx` dice que el
   `session_id` hace sobrevivir la conversación; el código no pide
   el transcript ni el listado.
2. **«Chat nuevo» borra el pasado.** `resetThread()` manda `DELETE`
   a la sesión activa. Eso era correcto cuando no había historial:
   dejar la fila viva era dejar memoria colgada. Con historial,
   borrar al empezar otro chat es tirar el transcript que el
   operador acaba de construir.
3. **Las citas reabiertas no caben en el tipo de hoy.**
   `SessionView` en `types.ts` no tiene `history`. `CitationList`
   exige `SearchHit.text`. Un snapshot del servicio no trae el
   chunk: pintarlo como hit completo inventaría prosa.

Depende de `add-conversation-history` (rama
`add-conversation-history-ai-service`). Si esos endpoints no están
arriba, la pantalla degrada: lista vacía + aviso, el chat sigue
andando. No se finge el relay.

## What Changes

- Espejo del contrato en `lib/ai-service/types.ts`:
  `CitationSnapshot`, `HistoryTurn`, `SessionSummary`; `SessionView`
  gana `title`, `history`, `created_at`, `updated_at`.
- Cliente: `listAnswerSessions`, `renameAnswerSession`. `patchJson`
  en `base-client.ts` — el verbo no existe hoy y el servicio usa
  PATCH, no PUT. No es dependencia nueva.
- Route Handlers: `GET /api/answer/sessions` (query `limit` /
  `offset` de largo, sin re-declarar techos). `PATCH
  /api/answer/session/[sessionId]`. El GET por id ya existe; el
  body ensanchado pasa de largo.
- **Lista de hilos dentro de `/answer`**, no un ítem nuevo de
  `CONSOLE_MODULES`. Columna a la izquierda del chat (sheet en
  viewport chico). Título, fecha, `turn_count`. Tokens del tema,
  sin hex.
- **Reabrir.** Click en un resumen → `GET` del id → el hilo se
  arma desde `history` (pregunta, respuesta entera, snapshot de
  citas, `grounded`, anchors). La URL queda
  `/answer?session=<id>` para que un F5 restaure el mismo hilo.
- **Chat nuevo no borra.** Limpia el estado local, saca el query
  param, y el próximo `ask()` crea otra sesión. `DELETE` pasa a
  ser acción explícita de la lista (como un chat que se tira).
- **Citas reabiertas.** `CitationList` acepta snapshot: si no hay
  `text`, muestra `document_id` + título + sección. No se inventa
  el chunk.
- Renombrar: editar el título de la fila activa (PATCH). Vacío →
  el 422 del servicio, mostrado como error de la lista.

**Deliberadamente afuera:**

- Aislar la lista por usuario de Auth.js. El servicio no tiene
  dueño; filtrar en el BFF sería mentir. Todos los operadores del
  tenant ven los mismos hilos — igual que el GET del servicio.
- Títulos por LLM, streaming, página `/answer/[id]`.
- Suite de tests de UI.

**Dependencia nueva:** `thinking-orbs` (cero deps de runtime). El
panel «orquestador trabajando» era una lista de puntos; el
operador no veía el paso vigente. El orb cubre los nueve estados
de un thinking indicator y se mapea al nodo activo (`searching`
en retrieve, `composing` en síntesis). Las filas siguen en
Tailwind (`animate-in`, `pulse`); el paquete no reemplaza el
layout. Justificado: pedido explícito de UX del panel en vivo,
no un cliente HTTP ni un SDK de streaming.

## Capabilities

### New Capabilities
- Ninguna.

### Modified Capabilities
- `web-console`: `/answer` lista, reabre y no borra al empezar
  otro chat. El compositor y el camino agentico no cambian.

## Impact

- `business-backend/lib/ai-service/types.ts`
- `business-backend/lib/ai-service/base-client.ts` — `patchJson`
- `business-backend/lib/ai-service/answer.ts`
- `business-backend/app/api/answer/sessions/route.ts` (nuevo)
- `business-backend/app/api/answer/session/[sessionId]/route.ts`
  — `PATCH`
- `business-backend/app/(console)/answer/page.tsx` — lee
  `searchParams.session`
- `business-backend/app/(console)/answer/answer-console.tsx` —
  lista, rehidratación, chat nuevo, borrar, rename
- `openspec/standards/app-routes.md` — filas BFF
- `openspec/changes/add-answer-history-console/specs/web-console/spec.md`

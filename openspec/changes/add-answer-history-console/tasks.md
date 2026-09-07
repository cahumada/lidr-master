# Implementation Tasks

Depende de `add-conversation-history` en el servicio. Esta rama
no toca `ai-service/`.

## 1. Contrato en la consola

- [x] 1.1 Espejar en `lib/ai-service/types.ts`:
      `CitationSnapshot` (`document_id`, `document_title`,
      `section`, `bullet_path`, `content_hash`), `HistoryTurn`,
      `SessionSummary` (`session_id`, `title`, `created_at`,
      `updated_at`, `turn_count`). `SessionView` suma `title`,
      `history`, `created_at`, `updated_at` sin sacar los campos
      de memoria.
- [x] 1.2 `patchJson` en `lib/ai-service/base-client.ts`, mismo
      patrón que `putJson`. Sin paquete nuevo.
- [x] 1.3 En `lib/ai-service/answer.ts`: `listAnswerSessions({
      limit?, offset? })` → `GET /answer/sessions`;
      `renameAnswerSession(id, title)` → `PATCH
      /answer/session/{id}`. `readAnswerSession` no cambia de
      firma; el tipo de retorno se ensancha solo.

## 2. Route Handlers

- [x] 2.1 `app/api/answer/sessions/route.ts` — `GET`. Reenvía
      `limit` y `offset` si vienen; no re-declara default 50 /
      max 100. `toErrorPayload` en el catch. 200 + lista (un
      `[]` del servicio es éxito).
- [x] 2.2 `PATCH` en
      `app/api/answer/session/[sessionId]/route.ts`. Body JSON
      `{ title }`; si no parsea o falta `title`, 400. 422/404
      del servicio se reenvían. GET y DELETE no se tocan.

## 3. Pantalla

- [x] 3.1 `page.tsx` lee `searchParams.session` y se lo pasa a
      `AnswerConsole` como `initialSessionId`. Facets y perfiles
      siguen degradando si el servicio no responde.
- [x] 3.2 Columna de hilos en `answer-console.tsx` (sheet en
      `use-mobile`). Carga `GET /api/answer/sessions` al montar
      y después de cerrar un turno. Vacía: texto, no error.
      Falla de red: `Alert` con el `error` del BFF. Tokens del
      tema, sin hex.
- [x] 3.3 Elegir un resumen setea el `session_id`, pide
      `GET /api/answer/session/{id}` y arma el hilo desde
      `history` + `anchors`. `router.replace` a
      `/answer?session=<id>`. 404 → compositor vacío + alerta.
- [x] 3.4 Mapear `HistoryTurn` a `ChatTurn` cerrado. Citas sin
      `text` no inventan chunk: `CitationList` muestra badge +
      título + sección. Sin panel de flujo en turnos reabiertos.
- [x] 3.5 «Chat nuevo» limpia estado local y el query param.
      **No** manda `DELETE`. El próximo `ask()` crea sesión
      (sigue perezoso).
- [x] 3.6 Borrar en la lista: `DELETE`. Si era el activo, mismo
      estado que chat nuevo. Renombrar la fila activa: PATCH;
      422 se muestra, no se traga.
- [x] 3.7 Corregir el comentario de `answer-console.tsx` que
      afirma que el reload ya sobrevive. Sin ítem nuevo en
      `CONSOLE_MODULES`.

## 4. Specs y rutas

- [x] 4.1 Delta
      `openspec/changes/add-answer-history-console/specs/web-console/spec.md`
      alineado con lo implementado. El scenario «hilo nuevo» ya
      no exige `DELETE`.
- [x] 4.2 Filas BFF en `openspec/standards/app-routes.md`:
      `GET api/answer/sessions`, `PATCH
      api/answer/session/[sessionId]`. Actualizar la descripción
      del GET por id. Sin filas nuevas de página.

## 5. Verificar

- [x] 5.1 `pnpm lint` y `pnpm build` desde `business-backend/`.
- [ ] 5.2 En el browser, claro y oscuro:
      - un chat de ≥2 turnos, F5, el hilo vuelve con citas (sin
        inventar `text`);
      - chat nuevo deja el anterior en la lista;
      - borrar el activo vacía el compositor;
      - rename y 404 de un id vencido.
      Si el servicio de historial no está desplegado, declarar
      qué no se pudo clickear y que la lista degradó.
- [x] 5.3 `python scripts/validate_specs.py` desde la raíz, sin
      errores. Sin cambios de `frontend-standards.md` ni
      `bff-standards.md` (salvo proponer `patchJson` en el
      inventario del cliente si al implementar se ve el hueco —
      no editar el estándar en silencio).

# Implementation Tasks

## 1. Contrato en la consola
- [x] 1.1 Espejar en `lib/ai-service/types.ts` las formas de
  `ai-service/app/api/business_db.py`: `ExtractionRunItem` (con
  `can_activate`, las tres banderas, `status`, `is_active`),
  `ActiveRunInfo` (`origin`: `selected` | `default` | `none`),
  `CorpusStampInfo`, `ExtractionRunList`, `ActivateRunRequest`,
  `ActivateRunResponse`. `ServiceConfig.business_db` opcional, espejo
  de `BusinessDbView` en `GET /config`.
- [x] 1.2 Cliente `lib/ai-service/business-db.ts` (`server-only`):
  `listRuns()` y `activateRun(runId, body?)`. No importa otros
  contextos ni `lib/auth/`.
- [x] 1.3 `GET app/api/business-db/runs/route.ts` — relay a
  `GET /business-db/runs`. `toErrorPayload` si falla.
- [x] 1.4 `POST app/api/business-db/runs/[runId]/activate/route.ts` —
  relay a `POST /business-db/runs/{run_id}/activate`. JSON inválido
  → 400. 404 y 409 del servicio se reenvían. El handler no inventa
  `activated_by`: reenvía el body o `{}`.

## 2. Pantalla
- [x] 2.1 `app/(console)/(admin)/business-db/page.tsx` (Server
  Component): `listRuns()` en el servidor; falla → lista vacía +
  mensaje, no error page. Pasa `declaredBy` desde la sesión
  (`email` o `name`). `PageFrame` + `PageIntro`.
- [x] 2.2 `business-db-console.tsx`: encabezado con vigente, origen y
  sello (desfasaje visible cuando `stamp.matches_active` es false).
  Tabla de **todas** las corridas. Activar solo si `can_activate` y
  no `is_active`. Incompletas visibles, sin botón. Confirmar antes
  de POST. 409/404 se muestran con el `error` del BFF. Tokens del
  tema, sin hex.
- [x] 2.3 Ítem en `CONSOLE_MODULES` (Configuración, `administrador`):
  `/business-db`, título «Corridas».
- [x] 2.4 Filas en `openspec/standards/app-routes.md`: página
  `(console)/(admin)/business-db/page.tsx` y los dos handlers.
  Sacar el párrafo que dice que `/business-db/*` todavía no tiene
  Route Handler.

## 3. Verificar
- [x] 3.1 `pnpm lint` y `pnpm build` desde `business-backend/`.
  **2026-09-11**: ambos en verde; `/business-db` y los dos handlers
  aparecen en el build.
- [ ] 3.2 En el browser (claro y oscuro): abrir `/business-db` como
  administrador; ver todas las corridas; una sin `loaded_data` no se
  activa; una con datos se activa y pasa a vigente; un `usuario`
  recibe el 403 del grupo admin. Anotar qué no se pudo clickear
  (p. ej. si el mirror local no tiene una corrida incompleta).
  **Pendiente de verificación manual en browser** — lint/build OK;
  no hubo sesión de click-through en esta implementación.

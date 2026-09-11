## Why

`add-extraction-run-selection` ya eligió **una** corrida del mirror
VisualTIME, con listado y activación en FastAPI
(`GET /business-db/runs`, `POST /business-db/runs/{run_id}/activate`).
La consola no. Quien opera el producto no puede ver las corridas ni
cambiar la vigente sin hablarle al servicio a mano. Esa pantalla
quedó diferida a propósito (task 7.3 del change archivado) y
`app-routes.md` lo dice: no hay Route Handler ni página.

El enunciado de este change: **ver todas** las corridas que el
mirror tiene para el cliente, y **elegir solo las que están
completas**. Completa, en este sistema, no es el `status` del
extractor —ese campo arranca en `partial` y las tres cargas son
independientes (`openspec/domain/visualtime-database-metadata.md`
§2). Completa es `loaded_data = true`, que el contrato ya expone
como `can_activate`. Activar una corrida sin `business_data` deja
todos los códigos sin resolver y el servicio respondiendo peor
sin decir por qué; el 409 ya existe.

Verificado contra `business-backend/` en `main`:

1. **Sin espejo.** `types.ts` no declara las formas de
   `/business-db/runs`. `GET /config` ya trae `business_db` y el
   tipo `ServiceConfig` lo tira.
2. **Sin cliente ni BFF.** `lib/ai-service/` no tiene contexto
   `business-db`. `app-routes.md` anuncia los handlers como
   «cuando esa pantalla entre».
3. **Sin pantalla ni nav.** No hay `/business-db`. Un
   administrador no tiene dónde elegir.

El contrato de FastAPI **no cambia**. Si el servicio desplegado
todavía no tiene los endpoints, la página degrada: lista vacía +
el `error` del BFF, sin fingir un relay.

## What Changes

- Espejo en `lib/ai-service/types.ts`: `ExtractionRunItem`,
  `ActiveRunInfo`, `CorpusStampInfo`, `ExtractionRunList`,
  `ActivateRunRequest` / `ActivateRunResponse`. `ServiceConfig`
  gana `business_db` opcional (el campo ya viaja en `GET /config`).
- Cliente nuevo `lib/ai-service/business-db.ts`: `listRuns()` y
  `activateRun(runId, { activated_by? })`. Un contexto, no un
  `fetch` en el handler.
- Route Handlers: `GET /api/business-db/runs` y
  `POST /api/business-db/runs/[runId]/activate`. Relay delgado;
  404 y 409 viajan tal cual. El body de activación se reenvía;
  el handler no inventa `activated_by`.
- **Pantalla `/business-db`**, admin (grupo `(admin)/`), módulo
  Configuración. Lista **todas** las corridas (más nueva primero,
  como el servicio). El botón de activar solo en las que
  `can_activate` y no están vigentes. Las incompletas se ven, con
  las tres banderas y el `status` del extractor, y no se pueden
  elegir. Encabezado: vigente + origen (`selected` / `default` /
  `none`) + sello del corpus al lado cuando no coincide.
- `activated_by` lo declara la sesión de la consola (email, o
  nombre si no hay email). Lo pasa el Server Component al cliente;
  el handler solo reenvía. Ausente si la sesión no tiene con qué
  firmar — no se escribe `"unknown"`.
- Confirmar antes de activar: cambia con qué corrida se responde.
- Filas nuevas en `CONSOLE_MODULES` y en `app-routes.md`. El
  párrafo que dice «todavía no hay handlers» se reemplaza por las
  dos filas.

**Deliberadamente afuera:**

- **Filtrar por `status === "completed"`.** Ese vocabulario no es
  el gate del servicio y `status` arranca en `partial`. Pedir un
  segundo candado en FastAPI es otro change, con medición.
- **Crear o borrar corridas.** El mirror es de solo lectura desde
  acá; lo escribe `dw-oracle-extractor`.
- **Pintar el bloque `business_db` del chat.** Eso es contexto de
  respuesta (`add-business-db-context`), no elección de corrida.
- **Ítem de nav para no-admin.** Activar escribe configuración.
- Suite de tests de UI. Sin dependencias nuevas.

## Capabilities

### New Capabilities
- Ninguna.

### Modified Capabilities
- `web-console`: `/business-db` lista las corridas del mirror y
  deja activar solo las que tienen datos cargados.

## Impact

- `business-backend/lib/ai-service/types.ts`
- `business-backend/lib/ai-service/business-db.ts` — nuevo
- `business-backend/app/api/business-db/runs/route.ts` — nuevo
- `business-backend/app/api/business-db/runs/[runId]/activate/route.ts` — nuevo
- `business-backend/app/(console)/(admin)/business-db/page.tsx` — nuevo
- `business-backend/app/(console)/(admin)/business-db/business-db-console.tsx` — nuevo
- `business-backend/lib/console-nav.ts`
- `openspec/standards/app-routes.md`

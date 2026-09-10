## Why

`add-llm-usage-accounting` ya extrae, persiste y agrega el usage
de cada completion de chat (`GET /usage/summary`, campo `usage`
en las respuestas agenticas). La consola no. Tres huecos, todos
verificados contra `business-backend/` en `main`:

1. **El contrato no tiene espejo.** `types.ts` no tiene
   `TokenUsage` ni `UsageSummary`. El BFF no tiene
   `/api/usage/summary`. El browser no puede pedir el ledger
   sin ver `AI_SERVICE_URL`.
2. **No hay pantalla.** El operador que quiere saber qué se
   gastó abre la consola del proveedor. El servicio ya agrega
   por modelo y por sesión; nadie lo pinta.
3. **El turno en vivo tira el dato.** El grafo ya devuelve
   `usage` en el 200/202/progreso. `ChatTurn` no lo tiene, así
   que una completion cobrada se ve igual que un «sin
   contexto» que no llamó al modelo.

Depende del contrato de `add-llm-usage-accounting`, ya en
`main` (`GET /usage/summary`, `usage` en las respuestas
agenticas). Si el servicio desplegado todavía no lo tiene,
`/usage` degrada: ceros + aviso, el chat sigue andando. No
se finge el relay.

## What Changes

- Espejo del contrato en `lib/ai-service/types.ts`: `TokenUsage`,
  `UsageByModel`, `UsageSummary`. Las respuestas agenticas
  (`AnswerAgenticCompleted`, `Paused`, `Progress`) ganan
  `usage` con default ceros / `reported: false`.
- Cliente nuevo `lib/ai-service/usage.ts` — un contexto, no un
  `fetch` en el handler. `getUsageSummary({ from?, to?,
  session_id?, purpose? })` reenvía lo que venga; no re-declara
  techos.
- Route Handler `GET /api/usage/summary`: query de largo, 422
  del servicio se reenvía. El tenant no se acepta en el BFF:
  lo pone el servicio.
- **Pantalla `/usage`**, admin, módulo Configuración (nav
  `Uso`, junto a Modelos). Totales del tenant, tabla por
  proveedor+modelo,   filtros `from` / `to` / `purpose` /
  `session_id`. Al abrir, `from`/`to` son el mes en curso
  (Argentina). Ledger vacío = ceros y una frase, no un
  error. Tokens del tema, sin hex.
- **El turno en vivo muestra la última completion** cuando
  `reported` es true. Un turno reabierto desde `history` no
  inventa tokens: `HistoryTurn` no los trae.

**Deliberadamente afuera:**

- **Precio en USD.** El servicio no lo calcula. El enlace a la
  tabla de precios del proveedor ya vive en Modelos.
- **Embeddings / reranker / rebuild.** Otro ciclo de vida.
- **Filtro por usuario.** El servicio no tiene dueño. Mentir
  un corte en el BFF sería lo mismo que filtrar el historial
  de chats.
- **`usage` adentro de `HistoryTurn`.** El transcript es
  procedencia; el ledger se pregunta con
  `GET /usage/summary?session_id=`.
- **Ítem de nav para operadores no-admin.** El gasto del
  tenant es de quien configura proveedores.
- Suite de tests de UI. Sin dependencias nuevas.

## Capabilities

### New Capabilities
- Ninguna.

### Modified Capabilities
- `web-console`: `/usage` muestra el agregado del tenant.
  El chat pinta el `usage` de la última completion del
  turno en vivo. El compositor y el historial no cambian
  de contrato.

## Impact

- `business-backend/lib/ai-service/types.ts`
- `business-backend/lib/ai-service/usage.ts` — nuevo
- `business-backend/app/api/usage/summary/route.ts` — nuevo
- `business-backend/app/(console)/(admin)/usage/page.tsx`
- `business-backend/app/(console)/(admin)/usage/usage-console.tsx`
- `business-backend/lib/console-nav.ts` — ítem admin
- `business-backend/app/(console)/answer/answer-console.tsx`
  — `ChatTurn.usage`; no se toca `historyToTurns` para
  inventar números
- `openspec/standards/app-routes.md` — fila de página y de BFF
- `openspec/changes/add-llm-usage-console/specs/web-console/spec.md`

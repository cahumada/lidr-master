## Why

`add-window-status-metadata` ya está en `main`: cada `SearchHit` y cada
`ChunkMetadata` pueden llevar `window_status` (el nombre declarado por
`TABLE26`: `Activo`, `Acceso restringido`, `En proceso de instalación`).
El modelo lo lee en el bloque de evidencia. La consola no.

Verificado contra `business-backend/` en `main`:

1. **El espejo está atrasado.** `lib/ai-service/types.ts` no declara
   `window_status` en `SearchHit` ni en `ChunkMetadata`. Una pantalla
   no puede leer un campo que el tipo no nombra.
2. **La búsqueda no muestra el estado.** `Hit` en
   `search-console.tsx` pinta `document_id`, título, módulo, sección y
   ramas. Un hit de `MGSL006` (acceso restringido, 570 documentos en
   esa clase) se ve igual que uno de `CA014`.
3. **Las citas del chat tampoco.** `CitationList` y el recorte local
   `CitationView` no tienen el campo. El operador lee una respuesta
   citada sin saber si la transacción está contemplada.
4. **La vista previa de ingesta tampoco.** La tabla de chunks muestra
   sección y tipo; el estado que el chunker acaba de estampar no
   aparece.

El change de metadata dejó **fuera de alcance, a propósito**, un
filtro `window_status` en `/search`: *ocultar* lo no contemplado es
una decisión de producto, y fingir el recorte en el BFF haría que el
operador crea que filtró mientras FastAPI ignora el query param.
`GET /search` y `POST /answer` todavía no aceptan `window_status`.
Este change hace que el operador **lo vea**. Recortar es otro change
(`add-window-status-filter` en el servicio, y su espejo web).

Depende del contrato de `add-window-status-metadata`, ya en `main`.
Si el servicio desplegado todavía no trae el campo, la UI degrada:
sin badge, sin inventar `Activo`. No se finge el relay de un filtro
que no existe.

## What Changes

- Espejo en `lib/ai-service/types.ts`: `SearchHit.window_status` y
  `ChunkMetadata.window_status` (`string | null`). Ausente = no
  resuelto; **no** se lee como vigente.
- **Búsqueda.** Cada hit muestra el estado declarado **solo cuando
  está resuelto y no es `Activo`**, la misma regla que
  `render_hit_block`. Tokens del tema, nunca la palabra "baja".
- **Chat.** `CitationList` (citas en vivo de `SearchHit`) muestra el
  mismo badge. Un turno reabierto desde `history` **no** inventa
  estado: `CitationSnapshot` no lo trae.
- **Ingesta.** La vista previa muestra el estado en el documento o
  en la fila del chunk, con la misma regla. No persiste nada.
- Un componente chico compartido (`WindowStatusBadge`) para que las
  tres pantallas no diverjan en la regla. Tres call sites es el
  umbral del estándar de frontend.

**Deliberadamente afuera:**

- **Filtro `window_status` en búsqueda o en el chat.** El servicio no
  lo acepta. Un checkbox que manda el param sería un recorte falso.
  Va en `add-window-status-filter` (`-ai-service`) y su espejo web.
- **Default "solo Activo".** Sería ocultar 574 documentos sin que
  nadie lo pida. El default sigue siendo "todos".
- **Etiqueta "sin estado" / "baja".** La ausencia no es un valor del
  catálogo. "Baja" lo inventaría.
- **`window_status` en `CitationSnapshot`.** El transcript durable no
  lo guarda; estamparlo es un change del servicio.
- **Ítem de nav ni ruta nueva.** Se tocan pantallas que ya existen.
- Suite de tests de UI. Sin dependencias nuevas.

## Capabilities

### New Capabilities

- Ninguna.

### Modified Capabilities

- `web-console`: búsqueda, citas en vivo del chat y vista previa de
  ingesta muestran el estado declarado de la ventana cuando no está
  contemplada. `web-console` todavía no está en `openspec/specs/` —
  `add-web-console` sigue en curso — así que el delta vive acá.

## Impact

- `business-backend/lib/ai-service/types.ts` — `window_status` en
  `SearchHit` y `ChunkMetadata`
- `business-backend/components/window-status-badge.tsx` — nuevo
- `business-backend/app/(console)/search/search-console.tsx`
- `business-backend/app/(console)/answer/answer-console.tsx` —
  `CitationView` + `CitationList`; no se toca `historyToTurns` para
  inventar estado
- `business-backend/app/(console)/documents/ingest-console.tsx`
- `openspec/changes/add-window-status-console/specs/web-console/spec.md`
- Sin cambios de `app-routes.md`, `frontend-standards.md` ni
  `bff-standards.md`: no hay ruta nueva ni convención nueva

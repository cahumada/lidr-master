## Why

La consola tiene cinco pantallas en un nav plano. Quien entra a configurar un
modelo pasa por la misma lista que quien va a preguntar, y la pantalla de
respuesta es un formulario de una sola consulta: cada pregunta pisa la
anterior. Eso no es cómo se usa un asistente, y no agrupa el trabajo por lo
que la persona viene a hacer.

El dueño pidió tres módulos —**configuración** (agentes y modelos), **RAG**
(búsqueda, ingesta, corpus) y **respuesta** como chat— con componentes shadcn
que respondan al tema claro/oscuro que ya existe.

## What Changes

- Nav de sidebar agrupada en tres módulos, no una fila de cinco links.
- Configuración se parte en dos pantallas: tipos de agentes y modelos
  (proveedores + catálogo). Hoy viven en `/agents`.
- Respuesta pasa a un hilo de chat (burbujas, compositor abajo, historial de
  la sesión). Cada turno sigue siendo una corrida agentica independiente:
  el servicio no tiene memoria de conversación.
- Portada agrupada por módulo, no una tarjeta por pantalla suelta.
- Rutas viejas (`/agents` para modelos, etc.) no se rompen: modelos es
  `/models`; el resto conserva su URL.

**Deliberadamente afuera:**

- Persistencia del hilo en el servidor (el `thread_id` sigue siendo por
  corrida, no por conversación).
- Vercel AI SDK / streaming de tokens: el servicio todavía no streamea;
  el "pensar" sigue siendo el sondeo de progreso que ya existe.

## Capabilities

### New Capabilities
(ninguna)

### Modified Capabilities
- `web-console`: navegación por módulos, configuración partida, respuesta
  como chat de sesión.

## Impact

- `business-backend/app/layout.tsx`
- `business-backend/app/page.tsx`
- `business-backend/app/answer/page.tsx`
- `business-backend/app/answer/answer-console.tsx` → chat
- `business-backend/app/agents/page.tsx`
- `business-backend/app/agents/agents-console.tsx`
- `business-backend/app/models/` (nuevo)
- `business-backend/components/app-sidebar.tsx` (nuevo)
- `business-backend/components/ui/sidebar.tsx` y dependencias shadcn
- `openspec/changes/reorganize-console-modules/specs/web-console/spec.md`

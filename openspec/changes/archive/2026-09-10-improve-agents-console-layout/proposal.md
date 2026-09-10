## Why

`/agents` apila en un solo scroll el catálogo de tools, el sintetizador
con el system prompt abierto, los guardrails de sistema, el alta de
perfil y **todos** los perfiles nombrados a la vez, más las cinco
fichas deterministas. El texto vive en 10–11 px. El operador que llega
a configurar una persona o un modelo tiene que leer media página de
referencia antes de encontrar el formulario, y no hay un “este es el
agente / este es el perfil” que oriente la lectura.

El contrato no cambia: mismos campos, mismos Route Handlers, mismos
agentes de solo lectura. Duele la presentación.

## What Changes

- `/agents` pasa a un layout maestro–detalle: se elige un agente y se
  trabaja ese. El sintetizador (único configurable hoy) es la
  selección inicial.
- Los perfiles nombrados se eligen de a uno. El alta no compite con
  los editores abiertos.
- Prompt de sistema, guardrails de sistema y catálogo de tools quedan
  disponibles, cerrados por defecto: no ocupan la primera pantalla.
- El formulario de perfil se agrupa en secciones (identidad, voz,
  reglas, modelo). Acciones a la derecha. Borrar pide confirmación.
- Tipografía y aire al nivel del resto de la consola (`text-sm` /
  `text-xs`), no microcopy de 10 px.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `web-console`: la pantalla de agentes enfoca un agente y un perfil
  a la vez; la referencia (prompt, tools, guardrails de sistema) no
  se apila abierta.

## Impact

- `business-backend/app/(console)/(admin)/agents/page.tsx`
- `business-backend/app/(console)/(admin)/agents/agents-console.tsx`
- `openspec/changes/improve-agents-console-layout/specs/web-console/spec.md`

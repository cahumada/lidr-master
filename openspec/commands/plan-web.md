# plan-web

Proponer un change OpenSpec para la **consola Next completa**:
páginas, componentes **y** Route Handlers / `lib/ai-service/`
(`business-backend/`). No escribe código de producto.

El BFF no es un plan aparte: viaja con la pantalla que lo consume.
Si el change necesita un contrato nuevo en FastAPI, el plan de web
lo declara como dependencia de un change `-ai-service` (o de una
rama sin sufijo si el contrato y la UI aterrizan juntos).

## Argumentos

`$ARGUMENTS` puede ser:

- Un **change-id** kebab-case con verbo (`add-search-export`, `fix-theme-flash`).
- Un **ticket de Jira**. Si viene, se lee con el MCP; no se inventa clave.
- Una **frase** del problema. El agente deriva el change-id.
- Vacío: preguntar qué se quiere proponer.

## Rol

Arquitecto de la consola (App Router, React 19, Tailwind, shadcn, BFF
same-origin). Leé [frontend-standards.md](../standards/frontend-standards.md)
y [bff-standards.md](../standards/bff-standards.md) antes de escribir.

## Objetivo

Dejar un change listo para `develop-web`: qué se quiere ver, qué
Route Handler lo alimenta, y el checklist para construirlo.

## Proceso

### 1. Rama (obligatorio, primero)

1. `git fetch origin`
2. Buscar `<change-id>-web` (o `<change-id>` si ya está en curso).
3. Si no existe: desde `main` actualizado,
   `git checkout -b <change-id>-web`.
4. El change se escribe **en esa rama**.

### 2. Fuente de verdad

1. Specs de capability que la pantalla toca (`web-console`,
   `answer-orchestration`, …) en `openspec/specs/` o en el change
   en vuelo.
2. [frontend-standards.md](../standards/frontend-standards.md),
   [bff-standards.md](../standards/bff-standards.md),
   [app-routes.md](../standards/app-routes.md).
3. El código: `business-backend/app/`, `components/`, `lib/`.
4. Ticket de Jira si lo hay.
5. Una URL de diseño es opcional. Si el usuario la pasa, usarla; si
   no, el plan sale de la spec y de las pantallas hermanas. No
   inventar un flujo de diseño que el repo no usa.

El browser **nunca** llama a Railway. Toda llamada nueva es: tipo en
`lib/ai-service/types.ts` → método en el cliente del contexto →
Route Handler → console client. Si el endpoint todavía no existe en
FastAPI, el plan lo dice y no finge el relay.

### 3. Escribir el change

`openspec/changes/<change-id>/` con el formato de
[openspec/AGENTS.md](../AGENTS.md).

El `tasks.md` nombra archivos reales y cubre, cuando aplique:

- Ítem en `CONSOLE_MODULES` (`lib/console-nav.ts`) si hay pantalla nueva.
- `page.tsx` Server Component + `*-console.tsx` cliente.
- Cliente en `lib/ai-service/<contexto>.ts` y tipo en `types.ts`.
- Route Handler delgado (relay, `toErrorPayload`, status 202/409 si
  el servicio los usa).
- Fila nueva en [app-routes.md](../standards/app-routes.md).
- `pnpm lint` y `pnpm build` desde `business-backend/`.
- Verificación en browser del flujo tocado (o declarar qué no se
  pudo clickear).
- Claro y oscuro: ninguna pantalla nueva con color literal.

No agregar dependencias (ni el SDK de streaming de Vercel) sin
justificarlas en el proposal. No inventar suite de tests de UI.

### 4. Jira (solo si hay ticket)

Igual que [plan-ai-service](./plan-ai-service.md) §4: subtareas hijas
espejo de los grupos de `tasks.md`. Sin ticket, no se crea.

### 5. No implementar

Validar formato (`python scripts/validate_specs.py`). Siguiente
paso: [develop-web](./develop-web.md).

## Plantilla mínima de `tasks.md`

```markdown
# Implementation Tasks

## 1. Contrato en la consola
- [ ] 1.1 Espejar el schema en `lib/ai-service/types.ts`.
- [ ] 1.2 Método en el cliente del contexto (`lib/ai-service/…`).
- [ ] 1.3 Route Handler en `app/api/…/route.ts` — solo relay.

## 2. Pantalla
- [ ] 2.1 Server Component + console client.
- [ ] 2.2 Nav en `CONSOLE_MODULES` si es pantalla nueva.
- [ ] 2.3 Fila en `openspec/standards/app-routes.md`.

## 3. Verificar
- [ ] 3.1 `pnpm lint` y `pnpm build`.
- [ ] 3.2 Ejercer el flujo en el browser (claro y oscuro).
```

## Feedback sobre estándares

Si el plan revela un hueco en frontend/BFF/rutas, proponer el
parche al estándar y esperar aprobación.

# develop-web

Implementar un change OpenSpec en la **consola Next completa**
(páginas, componentes, BFF). El plan ya existe. No crea el PR.

## Argumentos

`$ARGUMENTS`: change-id, ticket mapeable a un change, o vacío
(change de la rama actual).

## Rol

Ingeniero de la consola. Estándares:
[frontend-standards.md](../standards/frontend-standards.md),
[bff-standards.md](../standards/bff-standards.md),
[app-routes.md](../standards/app-routes.md).

## Objetivo

Tachar el `tasks.md` del lado `-web`. El browser solo habla con
`/api/…`. `AI_SERVICE_URL` no sale del servidor.

## Proceso

### 1. Verificar que el change existe

1. Rama `<change-id>-web` o `<change-id>`. Si no hay rama ni
   carpeta de change, **parar** y pedir [plan-web](./plan-web.md).
2. Leé proposal, tasks y deltas. Leé las pantallas hermanas y
   `CONSOLE_MODULES` antes de crear una ruta.

### 2. Implementar

- Un ítem a la vez. Tachar al completar.
- Server Component para el fetch inicial; console client para
  interacción. Degradar a vacío/`null` si el servicio no responde.
- Capa HTTP: `lib/ai-service/` + Route Handler relay. Nada de
  `fetch` al host de Railway desde un Client Component.
- Tipos espejo 1:1 de Pydantic. El campo nuevo se agrega en
  `types.ts` **antes** de que la pantalla lo lea.
- Pantalla nueva: ítem en `CONSOLE_MODULES` y fila en
  `app-routes.md` en el mismo change.
- Tokens de tema, no hex. Verificar claro y oscuro.
- Reusar shadcn en `components/ui/` antes de inventar un control.
- No borrar páginas ni handlers de [app-routes.md](../standards/app-routes.md)
  salvo pedido explícito.
- Dependencia nueva: solo si el proposal la justificó.

Si una task es de FastAPI, no la implementes acá —
[develop-ai-service](./develop-ai-service.md).

Una URL de diseño es opcional. Si el usuario la pasa, usarla como
referencia visual; si no, seguir las pantallas hermanas.

### 3. Verificar

Desde `business-backend/`:

```bash
pnpm lint
pnpm build
```

Ejercer en el browser el flujo tocado (click, submit, estados
vacío/error). Un screenshot no alcanza. Si no hay browser tools,
decirlo.

Desde la raíz, si hubo deltas o cambios de estándares:

```bash
python scripts/validate_specs.py
```

### 4. Git

No commitear ni abrir el PR acá, salvo que el usuario lo pida.
Siguiente: [update-docs](./update-docs.md) si aplica,
[commit](./commit.md), [create-pr](./create-pr.md).

### 5. Jira (solo si hay subtareas del plan y ya existe el PR)

- Solo subtareas **de este plan** (consola).
- La historia padre se cierra **solo** si no quedan subtareas
  abiertas (incluido el lado `ai-service`).
- Comentario con la URL del PR.
- Sin ticket: no tocar Jira.

## Feedback sobre estándares

Proponer el parche al estándar, esperar aprobación, aplicar lo
acordado. No editar `openspec/standards/` en silencio.

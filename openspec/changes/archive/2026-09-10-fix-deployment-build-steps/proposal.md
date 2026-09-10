## Why

**El despliegue continuo está documentado pero nunca corrió de punta a punta**, y
las dos plataformas fallan por la misma razón: el repo asume pasos que en un
clone limpio nadie ejecuta.

### 1. El build de Vercel no puede compilar

[`lib/auth/prisma-client.ts:4`](../../../business-backend/lib/auth/prisma-client.ts)
importa `@/lib/generated/prisma/client`. Ese directorio:

- está gitignoreado (`/lib/generated/prisma` en
  [`business-backend/.gitignore`](../../../business-backend/.gitignore)), así que
  no viaja en el clone;
- lo produce `prisma generate`, que **nadie corre**: el script de build es
  `next build` a secas, y Prisma 7 no tiene hook de `postinstall` —
  `node_modules/prisma/package.json` solo declara `preinstall`.

En local funciona porque el directorio ya existe de una corrida vieja. En Vercel
el módulo no existe y `next build` corta con un error de TypeScript. Es un fallo
del **primer** deploy, no una degradación: hoy no hay ninguna URL viva.

### 2. Ninguna migración se aplica sola

El `CMD` del [Dockerfile](../../../ai-service/Dockerfile) arranca `uvicorn`
directo. El deploy copia `alembic/` y `alembic.ini` a la imagen y después no los
usa nunca. Cada migración nueva queda como un paso manual que nada recuerda, y
la forma que toma el olvido es un `UndefinedColumn` en la primera pregunta.

## What Changes

- **`prisma generate` entra al build de la consola.** Es el paso que falta para
  que un clone limpio compile, y no toca la base: genera código desde
  `schema.prisma`.
- **`alembic upgrade head` corre al arrancar el contenedor del servicio.** El
  servicio ya corre como **una sola instancia** en Railway —es la premisa del
  buffer en memoria de `activity.py`, documentada en su README— así que no hay
  dos procesos compitiendo por el lock de migración. Si la migración falla, el
  contenedor no levanta: eso es lo correcto, un servicio que responde con el
  esquema viejo miente.
- **Las migraciones de la consola quedan como un acto deliberado**, con script
  propio (`pnpm db:deploy`) y no dentro del build. Vercel construye en cada
  commit; una migración atada al build corre decenas de veces por semana y
  falla el deploy entero cuando la base está un segundo inalcanzable. El
  servicio migra al arrancar porque su deploy es uno por push de `ai-service/`;
  la consola no tiene esa propiedad.
- **La tabla de despliegue del README dice la verdad completa.** Hoy lista una
  sola variable para Vercel (`AI_SERVICE_URL`) y la consola necesita seis más
  desde que hay login. Se agregan además los dos pasos que no son del repo y sin
  los cuales el evaluador no entra: el redirect URI de Google y el alta del
  primer usuario (`pnpm seed:admin`), porque la consola no auto-provisiona.

Fuera de alcance:

- **Verificar el despliegue vivo.** Necesita las credenciales de las dos
  plataformas. Este change deja el repo en condiciones de que el deploy funcione;
  confirmarlo es el paso siguiente y se hace contra la URL pública.
- **Un job de CI que despliegue.** Sigue siendo lo que
  [`ci.yml`](../../../.github/workflows/ci.yml) dice que no hace: las dos
  plataformas ya despliegan desde GitHub con rollback.

## Capabilities

Ninguna. Es configuración de build y arranque: no cambia ningún comportamiento
que una spec afirme. El único efecto observable —el contenedor no levanta si la
migración falla— es sobre el despliegue, no sobre la API.

## Impact

- `business-backend/package.json` — `build` y un `db:deploy` nuevo.
- `ai-service/Dockerfile` — el `CMD` migra antes de servir.
- `README.md` — la tabla de despliegue y los pasos que no son del repo.

## Verificado (2026-09-10)

**El build de la consola, en la condición del clone limpio** (`lib/generated/prisma`
borrado, que es como llega a Vercel):

| build | resultado |
|---|---|
| `next build` — el script de antes | `Module not found: Can't resolve '@/lib/generated/prisma/client'`, exit 1 |
| `pnpm build` — con `prisma generate` | compila; 30 rutas, middleware incluido |

Es exactamente el fallo que el `Why` predice, reproducido y cerrado.

**La imagen del servicio**: `docker build` verde. Corrida contra una base
inalcanzable a propósito, el contenedor muere en la migración
(`OperationalError: connection refused`) y `uvicorn` **nunca arranca** — que es
la propiedad que se buscaba: sin esquema no hay servicio que responda.

`python scripts/validate_specs.py`: 0 errores.

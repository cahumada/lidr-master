# Visual Time RAG — consola web

El frontend y el backend de negocio: Next.js (App Router, TypeScript),
Tailwind y componentes [shadcn/ui](https://ui.shadcn.com). Uno de los dos
proyectos del repo; el otro es [`ai-service/`](../ai-service/README.md).
Portada del monorepo en el [README de la raíz](../README.md).

## Puesta en marcha

```bash
cd business-backend
pnpm install
cp .env.example .env.local     # ver las cuatro variables de abajo
pnpm db:deploy                 # crea las tablas de identidad
pnpm seed:admin                # la primera cuenta administradora
pnpm dev
```

Necesita el servicio IA corriendo:

```bash
cd ../ai-service && uv run uvicorn app.main:app --reload
```

Cuatro variables, y las cuatro son privadas — ninguna lleva `NEXT_PUBLIC_`:

| Variable | Para qué |
|---|---|
| `AI_SERVICE_URL` | El servicio IA. Si falta, toda llamada devuelve 500. |
| `AI_SERVICE_TOKEN` | El token compartido con el servicio. Sin él no se manda header, que es lo correcto contra un servicio abierto en desarrollo; contra uno con `SERVICE_TOKEN` puesto, todo responde 401. |
| `AUTH_SECRET` | Firma la cookie de sesión. `npx auth secret` la genera. |
| `AUTH_DATABASE_URL` | La base de **identidad**, que no es la del corpus. A propósito no se llama `DATABASE_URL`: ese nombre ya es el del corpus, y confundirlas es cómo las contraseñas terminan en un `pg_dump` del RAG. |

Google es opcional en desarrollo: sin `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET`
queda el login con correo y contraseña. Detalle de cada una en
[`.env.example`](.env.example).

### Migraciones de identidad

Prisma, y solo para las cinco tablas de identidad — el corpus lo migra
Alembic desde `ai-service/` y las dos herramientas no se cruzan.

```bash
pnpm db:deploy                       # prisma migrate deploy: aplica lo pendiente
pnpm exec prisma migrate dev --name  # crear una migración nueva (desarrollo)
pnpm seed:admin                      # promueve/crea la primera administradora
```

`pnpm build` corre `prisma generate` antes de `next build`, así que el cliente
generado (`lib/generated/prisma/`) nunca queda viejo respecto del esquema.
`db:deploy`, en cambio, **no** es un paso del build ni acá ni en Vercel: se
corre a mano, contra `AUTH_DATABASE_DIRECT_URL`. El porqué está en el
[README de la raíz](../README.md) — Vercel construye en cada commit, y una base
un segundo inalcanzable no tiene que voltear el deploy entero.

## Autenticación

Auth.js v5 con Google y correo + contraseña, sesión en JWT, y **dos roles**:
`usuario` consulta; `administrador` además configura el servicio y puede
disparar un rebuild destructivo del corpus.

Tres cosas que conviene saber antes de tocar una pantalla:

- **Registrarse no da acceso.** Una cuenta nueva nace `usuario` y
  deshabilitada, y espera en `/register/pending` hasta que un administrador la
  habilite. El default `usuario` está en la base y no solo en el código, para
  que una fila insertada a mano no nazca administradora.
- **Quién puede abrir qué lo decide dónde está el archivo.** Las pantallas de
  administración viven bajo `app/(console)/(admin)/` y las cierra el layout de
  ese grupo. El filtro del sidebar oculta lo que no se puede abrir, pero **no
  autoriza**: borrarlo no abre nada.
- **El borde es optimista.** `proxy.ts` solo pregunta si hay cookie, y la lee
  sin verificar la firma. La sesión real se resuelve en
  `app/(console)/layout.tsx`, cerca de los datos, donde está el secreto.

La mecánica completa —y por qué la identidad es la única excepción al «acá no
hay ORM»— está en
[`openspec/standards/bff-standards.md`](../openspec/standards/bff-standards.md)
§Identidad.

## El browser nunca habla con el servicio IA

Toda llamada al servicio sale **del servidor de Next**, desde los Route
Handlers de `app/api/`. El browser solo habla con el origen de esta app.

Eso no es una preferencia de estilo: conserva, sobre Vercel + Railway, la
misma propiedad que el `docker-compose` del curso obtiene teniendo un solo
servicio con puertos publicados. `AI_SERVICE_URL` es privada —sin prefijo
`NEXT_PUBLIC_`— y `AI_SERVICE_TOKEN` también: el servicio exige un token
compartido, y lo agrega `base-client.ts` en el servidor. Si el browser
hablara directo con el servicio, habría que mandarle el token al browser — o
sea, publicarlo.

`lib/ai-service/base-client.ts` importa `server-only`: intentar usarlo desde un
Client Component es un error de build, no un descuido que se descubre en
producción.

## Estructura

Los grupos entre paréntesis no aparecen en la URL: `(console)/(admin)/models/`
sirve `/models`. Están para el layout de cada grupo — y en `(admin)`, ese
layout es el que rechaza.

```
app/
├── api/                       # Route Handlers: el proxy hacia el servicio IA
│   ├── auth/[...nextauth]/    # Auth.js — el único que no es relay
│   ├── search/
│   ├── answer/agentic/ · answer/agentic/resume/
│   ├── answer/agentic/start/ · answer/agentic/[threadId]/progress/
│   ├── config/ · config/agents/[agentKey]/ · usage/summary/
│   ├── documents/ingest-file/
│   └── corpus/rebuild · jobs · jobs/[id]
├── (auth)/                    # sin sesión: login, register, register/pending
└── (console)/                 # con sesión: shell + gate
    ├── search/                # Búsqueda: la pantalla principal
    ├── answer/                # Respuesta agentica: formulario, traza y gate humano
    ├── documents/             # Vista previa de ingesta (no persiste)
    └── (admin)/               # solo `administrador`
        ├── agents/            # Catálogo de agentes y sus perfiles (persona, modelo)
        ├── corpus/            # Reconstrucción del corpus y sus trabajos
        ├── models/ · usage/
        └── users/             # Cuentas, roles y habilitación
lib/ai-service/                # LA ÚNICA capa que habla HTTP con el servicio
├── base-client.ts             # fetch, timeouts, el token y los errores del servicio
├── types.ts                   # espejo 1:1 de los schemas Pydantic
├── search.ts · documents.ts · corpus.ts · answer.ts · config.ts   # un cliente por contexto
lib/auth/                      # identidad: cliente Prisma, hashing, roles, barandas
components/ui/                 # shadcn: el código vive acá, no en node_modules
```

### Respuesta agentica (`app/(console)/answer/`)

No llama a `POST /answer/agentic` (el endpoint síncrono) sino a la variante
de progreso en vivo: `POST /answer/agentic/start` agenda la corrida y
devuelve un `thread_id` al instante, y la pantalla sondea
`GET /answer/agentic/{thread_id}/progress` cada 1,2 s (`POLL_INTERVAL_MS`)
mientras dura. Un panel **"Flujo en vivo"** anima los cuatro agentes
(planificador, recuperación, síntesis, validación) más el gate como
`idle` → `running` → `done`, con el último mensaje narrado de cada uno —
el mismo patrón que la rama `agents_event` del curso (sin streaming real:
es polling, pese al nombre).

Cuando `/progress` deja `running`, dos caminos:

- **`completed`** — se arma un `AnswerAgenticCompleted` con la respuesta,
  sus citas, y la traza de ruteo (`routing_history`) de los cuatro agentes.
- **`awaiting_human_review`** — la pantalla muestra el motivo (confianza
  baja, sin evidencia, cita sin respaldo) y botones para aprobar o rechazar
  (el schema también admite `adjust`, sin control propio todavía) que
  llaman a `POST /answer/agentic/resume` — **sin sondeo**, porque resumir es
  síncrono y devuelve el resultado final en la misma respuesta. El 202 de
  `/start` y de `/answer/agentic` no es un error: `base-client.ts` distingue
  explícitamente 200 de 202 (`postJsonAllowingStatuses`) para que ese caso
  no caiga en la misma rama que un fallo real.

### Agentes (`app/(console)/(admin)/agents/`)

Arma toda la pantalla desde `GET /config`: el rol de cada agente, sus
herramientas permitidas y su modelo vigente salen del servicio que corre el
grafo, no de una copia declarada acá — la consola no puede describir un grafo
que ya no existe.

Arriba, un panel de **proveedores** (`app/(console)/(admin)/agents/providers-panel.tsx`)
editable: habilitar o deshabilitar cada uno, su base URL cuando habla el
formato de OpenAI, la curaduría de sus modelos (mostrar, ocultar, quitar,
agregar a mano) y un botón **"Traer del proveedor"** que le pregunta al
proveedor qué modelos sirve. Los nuevos llegan ocultos: medido acá, OpenAI
reporta 124 y valen la pena 2.

La **credencial es write-only** y eso no es una convención de UI, es lo que
permite la API: no hay nada acá que pueda mostrar una clave guardada porque
ningún endpoint la devuelve. Lo que se ve es de dónde viene la que está vigente
(`env` o `stored`) y cuatro caracteres de ella, lo justo para distinguirla de
otra. Si el servicio no tiene `SECRETS_KEY`, el formulario no se ofrece y la
pantalla dice por qué en vez de dejar intentar algo que iba a fallar.

Un proveedor sin credencial usable aparece apagado y sus modelos van `disabled`
en el selector del agente — la consola no deja elegir algo que iba a fallar al
responder.

Dos secciones, porque los agentes no son iguales: el que **llama a un modelo**
(`answer_synthesizer`) tiene formulario de persona, modelo, temperatura y tope
de tokens, con un contador contra el tope de persona y un botón para volver a
los defaults; los **deterministas** son fichas de solo lectura que dicen por qué
no tienen nada que configurar.

El selector de modelo agrupa por proveedor y el par `proveedor:modelo` viaja
junto — el servicio valida el par, así que "gpt-4o bajo Anthropic" se rechaza en
vez de guardarse. Los modelos que **rechazan los parámetros de sampling** (los
Claude de esta generación devuelven 400 por `temperature`) quedan anotados
`· sin temperatura` y, al elegirlos, el campo de temperatura se deshabilita
diciendo por qué. Un campo vacío significa "usar el default del
servicio", y la pantalla marca cada valor vigente como `perfil` o `default del
servicio` para que no haya que adivinar.

La validación vive en el servicio (agente desconocido, agente determinista,
modelo fuera del catálogo, persona sobre el tope) y sus 404/422 viajan tal cual:
duplicar esas reglas acá sería un segundo lugar que mantener sincronizado.

Los contextos (`search`, `documents`, `corpus`, `answer`, `config`) **no se importan entre sí**, y
ninguna pantalla hace `fetch` al servicio por su cuenta: si falta una llamada,
se agrega al cliente del contexto que corresponde.

`types.ts` espeja los schemas de `ai-service/app/generation/rag/schemas.py` y
`ai-service/app/ingestion/schemas.py`. Cuando el servicio agrega un campo, se
agrega ahí **primero** — una pantalla no lee un campo que ese archivo no
declara.

## Comandos

```bash
pnpm dev          # desarrollo
pnpm lint         # eslint
pnpm test         # node --test sobre lib/auth/ (contraseñas, roles, barandas)
pnpm build        # prisma generate + next build; corre TypeScript
pnpm start        # servir el build
pnpm db:deploy    # prisma migrate deploy
pnpm seed:admin   # primera cuenta administradora
```

`pnpm test` cubre `lib/auth/` y nada más: no hay runner de UI. Lo que se
prueba es lo que no es relay — hashear y verificar una contraseña, resolver
un rol, sanear el `next` del login y las barandas de la pantalla de usuarios.

## Despliegue

Vercel, con **root directory `business-backend/`**. Las cuatro variables de
arriba se configuran en el proyecto Vercel, no en el repo, y `db:deploy` corre
antes del build. El detalle —y el filtro de rutas para que un commit del
servicio no dispare un build acá— está en el
[README de la raíz](../README.md).

Dos cosas que no viven en el repo, y sin ellas el despliegue queda arriba y
nadie puede entrar: el **redirect URI de Google**
(`https://<app>.vercel.app/api/auth/callback/google`, con `AUTH_URL` puesta a
ese mismo origen — detrás del proxy de Vercel, sin ella los callbacks se arman
contra el host interno y Google los rechaza) y el **alta del primer usuario**,
porque la consola no auto-provisiona: un login de Google con un email que no
está en la base se rechaza. Los dos pasos están en el
[README de la raíz](../README.md).

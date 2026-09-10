# Estándares del BFF (Next.js)

El backend de negocio de la consola: Route Handlers bajo
`business-backend/app/api/**/route.ts` y la única capa HTTP hacia el
servicio IA, `business-backend/lib/ai-service/`.

Esto **no** es el API de producto. El API de producto es FastAPI en
`ai-service/`. Acá no hay jobs propios ni dominio de seguros. Hay un
proxy same-origin para que el browser nunca vea `AI_SERVICE_URL`.

Hay **una** excepción de persistencia y está acotada **por enumeración**:
la identidad de la consola —usuarios, cuentas de proveedor, sesiones,
tokens de verificación y rol— vive en Postgres vía Prisma. Esas cinco
entidades y ninguna otra. Enumerada y no «persistencia de identidad» a
propósito: sin lista, es la puerta por la que entra una tabla de
preferencias, después una de favoritos, y el estándar dejó de decir algo.
Cualquier tabla fuera de esa enumeración es dominio, y el dominio vive en
el servicio. Ver [§Identidad](#identidad).

Páginas y componentes: [frontend-standards.md](./frontend-standards.md).
Servicio Python: [ai-service-standards.md](./ai-service-standards.md).

## Stack

| Capa | Tecnología |
|---|---|
| Runtime | Node 22 (CI); Next.js 16 App Router |
| Lenguaje | TypeScript strict (`business-backend/tsconfig.json`) |
| HTTP al servicio | `fetch` en `lib/ai-service/base-client.ts`, marcado `server-only` |
| Validación | La del servicio. El BFF solo rechaza lo que no puede reenviar |
| Lint / tipos | `pnpm lint` (eslint-config-next) y `pnpm build` (corre `tsc`) |
| Tests | `pnpm test` (`node --test` + `tsx`) sobre `lib/auth/` y nada más. Sin Jest ni Vitest. El contrato upstream se prueba en `ai-service/tests/api/` |

Comandos, desde `business-backend/`:

```bash
pnpm install          # lockfile: pnpm-lock.yaml; CI usa --frozen-lockfile
pnpm dev
pnpm lint
pnpm test             # lib/auth/ — ver §Tests
pnpm build
pnpm db:deploy        # migraciones de identidad — ver §Identidad
```

## Rol del BFF

```
browser  ──same-origin──►  Route Handler  ──AI_SERVICE_URL──►  FastAPI
                                 │
                                 └── lib/ai-service/{search,documents,corpus,answer,config}
```

Cuatro reglas que no se negocian (las tres primeras ya son capability
de `web-console`):

1. **El browser nunca llama al servicio IA.** Ni `NEXT_PUBLIC_AI_SERVICE_URL`,
   ni un `fetch` desde un Client Component al host de Railway.
2. **Una sola capa habla HTTP con el servicio.** `lib/ai-service/`: un
   cliente base más un cliente por contexto. Los contextos no se importan
   entre sí. Ninguna pantalla ni Route Handler hace `fetch(`${aiServiceUrl}`)`.
3. **La app web nunca llama a un proveedor de modelos.** Ni del lado del
   servidor. Si una pantalla necesita un LLM, el servicio expone un
   endpoint y el BFF lo reenvía.
4. **Todo Route Handler es relay, salvo el de autenticación.** La única
   excepción es `app/api/auth/[...nextauth]/route.ts`, que reexporta los
   `handlers` de Auth.js: la sesión pertenece al origen de esta app, no al
   servicio, así que no hay a quién reenviarla. Está anotado en el propio
   archivo. Otro handler que no sea relay necesita su propio proposal.

`server-only` es la garantía, no la convención: importar
`base-client.ts` desde un Client Component es error de build.

## Estructura

```
business-backend/
├── app/api/
│   ├── search/                 # GET, GET /facets
│   ├── documents/ingest-file/  # POST multipart
│   ├── corpus/                 # rebuild + jobs
│   ├── answer/                 # agentic + session
│   └── config/                 # agentes, perfiles, proveedores
└── lib/ai-service/
    ├── base-client.ts          # getJson / postJson / errores
    ├── types.ts                # espejo 1:1 de los schemas Pydantic
    ├── search.ts
    ├── documents.ts
    ├── corpus.ts
    ├── answer.ts
    └── config.ts
```

Un contexto nuevo (otro grupo de endpoints) es un archivo nuevo en
`lib/ai-service/`, no un `fetch` suelto en el Route Handler. El
handler queda en cinco a treinta líneas: parsear lo mínimo, llamar al
cliente, devolver JSON o `toErrorPayload`.

## Identidad

La excepción de la intro, con su forma. La introdujo
`add-console-authentication`; el porqué de cada decisión está en el
`design.md` de ese change.

```
business-backend/
├── auth.ts                     # Auth.js: proveedores, callbacks, strategy "jwt"
├── proxy.ts                    # gate de borde: ¿hay cookie de sesión?
├── prisma/schema.prisma        # las cinco entidades enumeradas, y nada más
└── lib/auth/
    ├── prisma-client.ts        # el ÚNICO lugar que abre una conexión a base
    ├── prisma.ts               # el mismo singleton + `server-only`
    ├── password.ts             # hash y verificación
    ├── roles.ts                # los dos roles; tabla pura, sin imports de base
    ├── guards.ts               # barandas de la pantalla de usuarios
    └── safe-redirect.ts        # el `next` del login, saneado
```

Cinco reglas:

1. **`lib/auth/` y `lib/ai-service/` no se importan entre sí.** Una habla
   Postgres por Prisma, la otra HTTP con FastAPI. Mezclarlas es cómo una
   consulta de negocio termina saliendo de la base equivocada.
2. **Base aparte de la del corpus, y su propia variable.**
   `AUTH_DATABASE_URL`, nunca `DATABASE_URL` —ese nombre ya es el del
   corpus—, sin `NEXT_PUBLIC_`. Alembic no ve estas tablas y un `pg_dump`
   del corpus no puede traer contraseñas.
3. **El rol se resuelve en el servidor.** `proxy.ts` responde una sola
   pregunta —¿hay cookie?— y **lee la cookie sin verificar su firma**: es
   un gate optimista en el borde, no autorización. La sesión real se
   resuelve en el layout, donde está el secreto.
4. **La pertenencia al grupo de administración es el file system.** Las
   pantallas que escriben configuración o destruyen datos viven bajo
   `app/(console)/(admin)/` y las cierra el layout de ese grupo. No una
   lista de paths comparada contra el pathname: un layout no recibe el
   pathname, y leer un header que puso el proxy falla **abierto** justo
   cuando el proxy se salteó.
5. **El filtro de la navegación no autoriza.** `lib/console-nav.ts` usa los
   roles para no mostrar lo que no se puede abrir; eso es presentación.
   Borrarlo no abre nada y agregarlo no cierra nada.

Prisma 7 toma un `adapter` de driver en vez de una `datasourceUrl`, así que
el pooling que necesitan las funciones serverless se configura en el `Pool`
de `pg` (`lib/auth/prisma-client.ts`), y la URL directa de las migraciones
vive en `prisma7.config.ts`.

## El Route Handler es transporte

Hace tres cosas y nada más:

1. Leer query / body / `FormData`. Si el JSON no parsea, 400. Si falta
   el campo sin el cual no hay nada que reenviar (`q`, `file`,
   `question`), 400 o 422.
2. Llamar al cliente del contexto.
3. Devolver el body del servicio con su status, o `toErrorPayload`.

No re-implementa el guard de `reset`, ni los defaults de `limit`, ni
la validación de `session_id`. Eso vive en FastAPI. Duplicarlo acá
crea una segunda fuente de verdad que se desincroniza.

```typescript
// Good — relay
export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q")
  if (!q) {
    return Response.json({ error: "Falta la consulta `q`.", status: 400 }, { status: 400 })
  }
  try {
    return Response.json(await search({ q, module_code: asList("module_code"), ... }))
  } catch (error) {
    const payload = toErrorPayload(error)
    return Response.json(payload, { status: payload.status })
  }
}

// Avoid — volver a declarar ge=1, le=100, default 10
```

Listas: `.getAll("module_code")`, no `.get`. FastAPI espera el query
param repetido (`?module_code=CA&module_code=DF`).

Multipart: no setear `Content-Type` a mano. `fetch` pone el boundary;
si se pisa, el servicio no puede parsear el body.

`cache: "no-store"` en todas las llamadas. Cada una es consulta viva
o mutación.

## Errores

`lib/ai-service/base-client.ts` distingue tres clases:

| Error | Origen | Status hacia el browser |
|---|---|---|
| `AiServiceError` | El servicio respondió no-OK | El mismo status + `detail` aplanado |
| `AiServiceUnreachable` | Red / timeout | 502, mensaje en español |
| Otro | Bug del BFF o `AI_SERVICE_URL` ausente | 500 genérico, sin stack |

`detail` de FastAPI puede ser string o lista de validación. `detailOf`
lo aplana a una línea. Nada interno se filtra.

Status que son *estado*:

- `202` en `POST /api/corpus/rebuild` y en `POST /api/answer/agentic`
  — éxito con cuerpo distinto, no error. Usar
  `postJsonAllowingStatuses` cuando el servicio puede devolver 200 o
  202.
- `409` en rebuild — “ya hay un job”. La UI lo muestra como estado.
- `204` en `DELETE /api/answer/session/{id}` — sin body.
  `deleteNoContent`, no `deleteJson` (`.json()` sobre vacío lanza).

Forma hacia el browser:

```typescript
{ error: string, status: number }
```

No inventar `{ success: true, data }` — el BFF no envuelve el contrato
del servicio. El JSON de un 200 es el del schema Pydantic, espejado en
`types.ts`.

## Tipos

`lib/ai-service/types.ts` espeja los schemas Pydantic 1:1. Cuando el
servicio agrega un campo, se agrega **ahí primero**, antes de que
ninguna pantalla lo lea.

- No renderizar JSON crudo.
- No acceder a un campo que el tipo no declara.
- No “arreglar” un nombre (`documentId` vs `document_id`): el wire es
  snake_case, como FastAPI.

## Configuración

- `AI_SERVICE_URL` — privada, sin `NEXT_PUBLIC_`. Si falta, el cliente
  lanza y `toErrorPayload` lo vuelve 500. El `next build` de CI no la
  define: el build no llama al servicio, y si algún día lo hiciera,
  esta ausencia es la que lo haría fallar.
- Timeouts: 30 s por defecto. Rebuild responde en milisegundos (devuelve
  un job id); una búsqueda con rerank tarda segundos. Subir el timeout
  en el cliente del contexto, no en el base, cuando el endpoint lo
  necesita.
- CORS: no. El browser y el BFF son el mismo origen. No agregar
  `Access-Control-Allow-Origin: *` a un Route Handler.

## Seguridad

- Nada de claves de OpenAI, Anthropic ni ningún vendor en este
  paquete. Viven en el servicio (env o `PUT /config/providers/{id}/key`).
- No loguear el body de una clave. Este BFF hoy no tiene un logger
  estructurado: no agregar `console.log` del request.
- Auth de personas: la consola autentica con Auth.js y el gate de rol se
  aplica **en el servidor** (ver `add-console-authentication`). No fingir un
  `protect()` donde no hay uno, y no deducir de la nav que una ruta esté
  cerrada: el filtro de la navegación no autoriza.
- Auth del servicio: toda llamada a `ai-service` lleva el token compartido, y
  lo agrega el **cliente base** — ninguna pantalla ni Route Handler lo maneja.
  La variable es `AI_SERVICE_TOKEN`, **sin** prefijo `NEXT_PUBLIC_`, que es el
  mecanismo que la expondría al browser. Sin configurar no se manda header: el
  servicio puede estar abierto a propósito en desarrollo, y en producción no
  arranca sin el suyo.
- Uploads: el archivo pasa de largo a `/documents/ingest-file`. Acá no
  se escribe a disco ni se persiste.

## Tests

Hay **un** runner y cubre **una** carpeta: `pnpm test` corre
`node --import tsx --test "lib/auth/*.test.ts"`. Node ya trae el runner y
`tsx` ya estaba para `seed:admin`, así que no se agregó ninguna dependencia
de test.

Esa es la respuesta a lo que este estándar dejaba abierto —«si el BFF crece
hasta tener lógica que no sea relay, el proposal justifica el runner»—. La
lógica que lo justificó es hashear y verificar una contraseña, resolver un
rol y sanear un redirect: nada de eso es relay y nada de eso se puede cubrir
desde `ai-service/tests/`. El alcance queda ahí:

- **Se testea** lo puro de `lib/auth/`: `password`, `roles`, `guards`,
  `safe-redirect`.
- **No hay runner** para páginas, formularios ni el flujo de OAuth, que
  necesita el proveedor real y se verifica en el browser.
- **El contrato upstream** se sigue cubriendo en `ai-service/tests/api/`.
- Un Route Handler nuevo que cambia el mapping de status (olvidar el
  202, tragarse un 409) es un bug de BFF: si no hay test acá, el
  checklist del change tiene que incluir una verificación explícita
  (`pnpm build` + ejercicio del flujo, o un test en el servicio que
  fije el status que el BFF debe reenviar).
- Sigue en pie el “no agregar Jest ni Vitest por las dudas”. Ampliar el
  alcance del runner —una suite de UI, por ejemplo— pide su proposal,
  igual que lo pidió éste.

## Workflow de este stack

- Rama con sufijo `-web` (páginas y BFF viajan juntos). Ver
  [git-workflow.md](./git-workflow.md).
- `pnpm lint`, `pnpm test` y `pnpm build` antes de dar el change por listo.
  Los tres corren en CI.
- Inventario: toda ruta nueva se agrega a
  [app-routes.md](./app-routes.md) en el mismo change.

## Despliegue (Vercel)

La consola —páginas **y** este BFF— se despliega en **Vercel**, no
en Railway. El API de producto sigue en Railway; Vercel solo habla
con él por `AI_SERVICE_URL`.

- **Root directory** `business-backend/`. Framework Next.js
  (`pnpm build` / `pnpm start`).
- **`AI_SERVICE_URL`:** URL pública del servicio en Railway.
  Privada, sin `NEXT_PUBLIC_`. Se configura en el proyecto Vercel,
  no en el repo. El `next build` de CI no la define: el build no
  llama al servicio.
- **Filtro de rutas:** `vercel.json` tiene `ignoreCommand` =
  `git diff --quiet HEAD^ HEAD -- .`. Si el commit no toca
  `business-backend/`, Vercel no construye. Un cambio solo en
  `ai-service/` no redespliega la consola.
- Los Route Handlers corren como funciones serverless de Vercel.
  Timeouts y cold start importan: un rebuild no se espera en el
  request (el servicio responde 202 + job id); una búsqueda con
  rerank cabe en el default de 30 s del cliente.
- CI **no** despliega. El merge a `main` que toca
  `business-backend/` es lo que dispara Vercel.

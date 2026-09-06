# Estándares del BFF (Next.js)

El backend de negocio de la consola: Route Handlers bajo
`business-backend/app/api/**/route.ts` y la única capa HTTP hacia el
servicio IA, `business-backend/lib/ai-service/`.

Esto **no** es el API de producto. El API de producto es FastAPI en
`ai-service/`. Acá no hay ORM, no hay jobs propios, no hay dominio
de seguros. Hay un proxy same-origin para que el browser nunca vea
`AI_SERVICE_URL`.

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
| Tests | No hay runner de Jest/Vitest en este paquete. El contrato se prueba en `ai-service/tests/api/` |

Comandos, desde `business-backend/`:

```bash
pnpm install          # lockfile: pnpm-lock.yaml; CI usa --frozen-lockfile
pnpm dev
pnpm lint
pnpm build
```

## Rol del BFF

```
browser  ──same-origin──►  Route Handler  ──AI_SERVICE_URL──►  FastAPI
                                 │
                                 └── lib/ai-service/{search,documents,corpus,answer,config}
```

Tres reglas que no se negocian (ya son capability de `web-console`):

1. **El browser nunca llama al servicio IA.** Ni `NEXT_PUBLIC_AI_SERVICE_URL`,
   ni un `fetch` desde un Client Component al host de Railway.
2. **Una sola capa habla HTTP con el servicio.** `lib/ai-service/`: un
   cliente base más un cliente por contexto. Los contextos no se importan
   entre sí. Ninguna pantalla ni Route Handler hace `fetch(`${aiServiceUrl}`)`.
3. **La app web nunca llama a un proveedor de modelos.** Ni del lado del
   servidor. Si una pantalla necesita un LLM, el servicio expone un
   endpoint y el BFF lo reenvía.

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
- Auth: no hay. No fingir un `protect()` ni un cookie check que no
  existe. Cuando entre, es un change con proposal.
- Uploads: el archivo pasa de largo a `/documents/ingest-file`. Acá no
  se escribe a disco ni se persiste.

## Tests

El BFF no tiene suite propia. Eso no autoriza a “probar a mano y ya”:

- El contrato upstream se cubre en `ai-service/tests/api/`.
- Un Route Handler nuevo que cambia el mapping de status (olvidar el
  202, tragarse un 409) es un bug de BFF: si no hay test acá, el
  checklist del change tiene que incluir una verificación explícita
  (`pnpm build` + ejercicio del flujo, o un test en el servicio que
  fije el status que el BFF debe reenviar).
- No agregar Jest “por las dudas”. Si el BFF crece hasta tener lógica
  que no sea relay, el proposal justifica el runner.

## Workflow de este stack

- Rama con sufijo `-web` (páginas y BFF viajan juntos). Ver
  [git-workflow.md](./git-workflow.md).
- `pnpm lint` y `pnpm build` antes de dar el change por listo.
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

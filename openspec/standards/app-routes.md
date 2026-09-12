# Rutas de la consola

Inventario de las páginas App Router y los Route Handlers que forman parte
de la consola publicada. Un agente **no los borra** salvo que el usuario
pida explícito sacar esa pantalla o ese endpoint.

Usar esta lista para:

- Verificar que las rutas críticas existen después de un refactor
- Restaurar una página si se eliminó por error (mismo path y patrón que
  las hermanas)
- Agregar la fila nueva **en el mismo change** que introduce la ruta

Paths de página relativos a `business-backend/app/`. Paths de API del BFF
relativos a `business-backend/app/api/`. El servicio IA vive en
`ai-service/` y se documenta al final: el browser **nunca** lo llama
directo.

Cuando una feature nueva agrega una ruta, se suma acá para que no se
borre después por “limpieza”.

## Páginas

Los **grupos de ruta no aparecen en la URL**: `(console)/(admin)/models/page.tsx`
sirve `/models`. Están para el layout de cada grupo, y en `(admin)` ese layout
**es** la autorización — ver §Layouts y shell.

La nav y la portada leen `lib/console-nav.ts`. Una pantalla nueva que no
esté en `CONSOLE_MODULES` no aparece en el sidebar ni en el home.

### Antes de la sesión — `(auth)/`

Las únicas páginas que `proxy.ts` deja pasar sin cookie.

| Path | Propósito |
|---|---|
| `(auth)/login/page.tsx` | Login: Google y correo + contraseña. Acepta `?next=` y lo saneada con `safe-redirect.ts` — un `next` externo no puede volverse un redirect abierto. |
| `(auth)/register/page.tsx` | Autoservicio de alta. La cuenta nace `usuario` y **deshabilitada**: registrarse no da acceso. |
| `(auth)/register/pending/page.tsx` | Donde espera quien se registró hasta que un administrador la habilite. Sin esta pantalla, un alta exitosa se veía igual que un fallo. |

### Con sesión — `(console)/`

Cualquier rol autenticado.

| Path | Propósito |
|---|---|
| `(console)/page.tsx` | Portada agrupada por los tres módulos del operador (Respuesta, RAG, Configuración). Sin métricas en vivo: `p@10` y los conteos salen de scripts, no de un endpoint. |
| `(console)/answer/page.tsx` | Chat agentico. Server Component: carga facets y perfiles del sintetizador; el hilo vive en `answer-console.tsx`. No usa `PageFrame`: el thread ocupa el inset entero. |
| `(console)/search/page.tsx` | Búsqueda híbrida con procedencia. Server Component precarga facets; falla de facets → lista vacía, no error page. |
| `(console)/documents/page.tsx` | Vista previa de chunking. **No persiste.** El corpus se construye en `/corpus`. |

### Solo `administrador` — `(console)/(admin)/`

Escriben configuración, destruyen datos o deciden quién entra. Mover una de
estas carpetas fuera del grupo la abre a cualquier sesión.

| Path | Propósito |
|---|---|
| `(console)/(admin)/corpus/page.tsx` | Rebuild (trocear, embeber, cargar) y seguimiento del job. Server Component lee identidad del corpus y jobs recientes para el guard de `reset`. |
| `(console)/(admin)/agents/page.tsx` | Catálogo de agentes desde `GET /config`. Persona, guardrails, tools. `dynamic = "force-dynamic"`. Degrada a catálogo vacío si el servicio no responde. |
| `(console)/(admin)/agents/flow/page.tsx` | Diagrama del grafo que corre `POST /answer/agentic`. Crear un perfil no agrega un nodo. |
| `(console)/(admin)/models/page.tsx` | Proveedores, catálogo de modelos, credenciales write-only. Un proveedor sin clave usable se deshabilita en la UI. |
| `(console)/(admin)/business-db/page.tsx` | Corridas del mirror VisualTIME: vigente, sello del corpus y activación solo con `loaded_data`. |
| `(console)/(admin)/usage/page.tsx` | Agregado de tokens de chat del tenant. Degrada a vacío + aviso si el servicio no responde. |
| `(console)/(admin)/users/page.tsx` | Cuentas, roles y habilitación. Las mutaciones son Server Actions (`users/actions.ts`), no Route Handlers. |

## Layouts y shell

Cuatro layouts, y **tres de ellos existen por la autenticación**. El de la
raíz quedó reducido a propósito: `/login` se renderiza antes de que haya
sesión, y un sidebar de pantallas que no se pueden abrir todavía cuenta qué
opera esta consola.

| Path | Propósito |
|---|---|
| `layout.tsx` | Solo el shell del documento: `<html lang="es">`, script de tema en `<head>`, favicon. Sin `className` en `<html>` — React lo resetearía al hidratar y borraría `dark`. |
| `(auth)/layout.tsx` | Una columna centrada, sin sidebar ni header. |
| `(console)/layout.tsx` | El chrome de la consola **y el gate de sesión**: llama a `auth()` y redirige a `/login` si no resuelve. `proxy.ts` ya rechazó lo que no traía cookie, pero lee la cookie **sin verificar la firma**: una falsificada pasa el borde a propósito y muere acá. |
| `(console)/(admin)/layout.tsx` | El gate de rol. Devuelve `<ForbiddenScreen />` si el rol no es `administrador`. La pertenencia es el file system, no una lista de paths: un layout no recibe el pathname. |
| `components/forbidden-screen.tsx` | El 403 con pantalla propia. **Dice 403 y el status HTTP es 200**: `forbidden()` exige `experimental.authInterrupts`. |
| `components/app-sidebar.tsx` | Sidebar; lee `visibleModules(role)`. El filtro es presentación — **no autoriza**. |
| `components/app-header.tsx` | Conmutador de tema, identidad de quien entró, salir y vincular Google. |
| `components/page-frame.tsx` | Columna con padding para pantallas-herramienta. El chat no la usa. |

## Route Handlers (BFF)

El browser solo habla con estas rutas. Cada una reenvía a `ai-service`
vía `lib/ai-service/`. No re-declarar defaults ni validación de negocio
que ya vive en el servicio; el BFF solo rechaza lo que no puede
reenviar (JSON inválido, `q` ausente, archivo ausente).

### Autenticación — la única que no es relay

| Path | Propósito |
|---|---|
| `api/auth/[...nextauth]/route.ts` | `GET`/`POST` — reexporta los `handlers` de Auth.js. El **único** Route Handler que no reenvía a FastAPI: la sesión es del origen de esta app, no del servicio. `bff-standards.md` §Rol del BFF admite esta excepción y ninguna otra. `proxy.ts` lo deja abierto — si no, entrar exigiría estar adentro. |

Las mutaciones de identidad **no** son Route Handlers: son Server Actions
(`(auth)/login/actions.ts`, `(auth)/register/actions.ts`,
`(console)/actions.ts`, `(admin)/users/actions.ts`). No agregar un endpoint
paralelo para lo que ya hace una action.

### Búsqueda e ingesta

| Path | Propósito |
|---|---|
| `api/search/route.ts` | `GET` — relay a `GET /search`. Requiere `q`. Listas (`module_code`, `window_type_name`) con `.getAll`, no `.get`. |
| `api/search/facets/route.ts` | `GET` — relay a `GET /search/facets`. |
| `api/documents/ingest-file/route.ts` | `POST` multipart campo `file` — relay a `POST /documents/ingest-file`. No escribe a disco. |

### Corpus

| Path | Propósito |
|---|---|
| `api/corpus/rebuild/route.ts` | `POST` — relay a `POST /corpus/rebuild`. Éxito `202`. El guard de `reset` vive en el servicio; este handler reenvía 400/409. |
| `api/corpus/jobs/route.ts` | `GET` — lista de jobs recientes. |
| `api/corpus/jobs/[id]/route.ts` | `GET` — estado de un job. |

### Respuesta agentica y sesión

| Path | Propósito |
|---|---|
| `api/answer/agentic/route.ts` | `POST` — relay a `POST /answer/agentic`. Reenvía 200 y **202** (pausa de revisión humana) como éxito. |
| `api/answer/agentic/start/route.ts` | `POST` — arranca el grafo en background (`POST /answer/agentic/start`). |
| `api/answer/agentic/resume/route.ts` | `POST` — retoma un thread pausado. |
| `api/answer/agentic/[threadId]/progress/route.ts` | `GET` — progreso en vivo de los nodos. |
| `api/answer/session/route.ts` | `POST` — crea sesión de conversación (`201`). El id lo emite el servicio, nunca el cliente. |
| `api/answer/sessions/route.ts` | `GET` — lista de conversaciones no vacías **de quien está logueado**. Reenvía `limit`/`offset` si vienen; un `[]` es éxito. |
| `api/answer/session/[sessionId]/route.ts` | `GET` memoria + transcript (`history`, `title`, timestamps); `PATCH` renombra; `DELETE` la descarta (204, idempotente). |
| `api/answer/session/[sessionId]/anchors/[kind]/[value]/route.ts` | `DELETE` — quita un anchor. |

Las cuatro rutas de sesión **no** llevan `requireAdmin`, y es a propósito:
`/answer` no es una pantalla de administración y cualquiera con sesión la usa.
Lo que las acota no es el rol sino el **dueño**: el BFF manda `X-Console-User`
con el `User.id` de Auth.js —en `lib/ai-service/base-client.ts`, el único lugar
que habla HTTP con el servicio— y el servicio filtra por él. Un rol de
administración no amplía lo que se ve. Sin sesión no va header, y el servicio lee
la ausencia como «las conversaciones que tampoco tienen dueño»: la falla es no
ver nada, nunca ver las de todos.

No hay Route Handler para `POST /answer` (un solo tiro). Ese camino lo
usa el eval del servicio, no la consola.

### Corridas del mirror

| Path | Propósito |
|---|---|
| `api/answer/prompts/[promptId]/route.ts` | `GET` — relay a `GET /answer/prompts/{id}`. **Chequea el rol ANTES de llamar al servicio**: `/answer` no es una pantalla de administración, así que ocultar el link es presentación y el 403 es la protección. Único route handler con gate de rol; ver `lib/auth/api-guards.ts`. |
| `api/business-db/tables/[name]/route.ts` | `GET` — relay a `GET /business-db/tables/{name}`. Diccionario completo de una tabla de la corrida activa. **Sin gate de rol**: el bloque de base ya se muestra en el turno a cualquier sesión. |
| `api/business-db/runs/route.ts` | `GET` — relay a `GET /business-db/runs`. Lista todas las corridas, la vigente y el sello del corpus. |
| `api/business-db/runs/[runId]/activate/route.ts` | `POST` — relay a `POST /business-db/runs/{run_id}/activate`. Reenvía 404 y 409 tal cual. `activated_by` lo declara quien llama. |

### Configuración

| Path | Propósito |
|---|---|
| `api/config/route.ts` | `GET` — catálogo de proveedores, modelos, agentes y flujo. |
| `api/config/agents/[agentKey]/route.ts` | `PUT` override del agente; `DELETE` lo vuelve a defaults. |
| `api/config/agents/[agentKey]/profiles/route.ts` | `POST` — crea un perfil nombrado. |
| `api/config/agents/[agentKey]/profiles/[profileId]/route.ts` | `PUT` / `DELETE` de un perfil. |
| `api/config/providers/[providerId]/route.ts` | `PUT` — metadatos del proveedor. |
| `api/config/providers/[providerId]/key/route.ts` | `PUT` guarda clave (write-only); `DELETE` la borra. Ninguna respuesta devuelve la clave. |
| `api/config/providers/[providerId]/models/route.ts` | `POST` — agrega un modelo al catálogo. |
| `api/config/providers/[providerId]/models/[model]/route.ts` | `PUT` / `DELETE` de un modelo. |
| `api/config/providers/[providerId]/models/refresh/route.ts` | `POST` — refresca el catálogo remoto del proveedor. |
| `api/usage/summary/route.ts` | `GET` — relay a `GET /usage/summary`. Reenvía `from` / `to` / `session_id` / `purpose` si vienen. No acepta `tenant_id`. |

## API del servicio IA (upstream)

El BFF es la única capa que llama estas rutas. Documentadas acá para
que un Route Handler nuevo no invente un path. Contratos en
`ai-service/app/generation/rag/schemas.py`, `app/domain/schemas.py` y
los módulos de cada router. Swagger en `/docs`.

| Método y path | Propósito |
|---|---|
| `GET /health` | Liveness. No pasa por el BFF. |
| `POST /documents/ingest` | Chunking por JSON (`filename`, `content`). No persiste. Pensado para llamadores programáticos. |
| `POST /documents/ingest-file` | Mismo chunking por upload UTF-8. |
| `GET /search` | Recuperación híbrida. Query `q` (min 2), filtros, ramas, rerank. |
| `GET /search/facets` | Módulos y tipos de ventana para los combos. |
| `GET /usage/summary` | Totales de tokens de chat del tenant. Filtros opcionales `from` / `to` / `session_id` / `purpose`. 422 si `from` > `to`. |
| `POST /answer` | Un tiro: retrieve → generate. Rechaza `session_id` con 422. |
| `POST /answer/agentic` | Grafo LangGraph. 200 o 202 (gate humano). |
| `POST /answer/agentic/start` | Igual, en background, para progreso en vivo. |
| `POST /answer/agentic/resume` | Retoma un thread. |
| `GET /answer/agentic/{thread_id}/progress` | Eventos de nodos. |
| `POST /answer/session` | Emite `session_id`. |
| `GET /answer/sessions` | Lista resúmenes **del dueño que dice `X-Console-User`** (`title`, `turn_count`, timestamps). Sin vacías ni vencidas. Paginado `limit`/`offset`. |
| `GET /answer/session/{session_id}` | Memoria (hechos, anchors, ventana) más `title`, `history` y timestamps. |
| `PATCH /answer/session/{session_id}` | Renombra. 422 si el título queda vacío. |
| `DELETE /answer/session/{session_id}` | 204 idempotente. |
| `DELETE /answer/session/{session_id}/anchors/{kind}/{value}` | Quita un anchor. |
| `POST /corpus/rebuild` | 202 + job id. La raíz del corpus sale de settings, no del body. |
| `GET /corpus/jobs` | Lista. |
| `GET /corpus/jobs/{job_id}` | Detalle. |
| `GET /answer/prompts/{prompt_id}` | El prompt tal como salió al modelo, mientras siga en la ventana de retención (`ANSWER_PROMPT_RETENTION_DAYS`, 7 días). `404` cuando no existe o ya se barrió — para quien pregunta es el mismo hecho. |
| `GET /business-db/tables/{table_name}` | Todo lo que la corrida ACTIVA declara de una tabla: columnas con descripción y tipo, PK, FK con su tabla destino, índices. Aparte del prompt a propósito — 12 tablas así son 15.969 tokens. `404` si la corrida no la tiene, `409` sin corrida activa. |
| `GET /business-db/runs` | Corridas del mirror de VisualTIME para este cliente, la vigente con su origen (`selected` / `default`) y el sello del corpus al lado. Solo lectura sobre `visualtime.*`. |
| `POST /business-db/runs/{run_id}/activate` | Elige con qué corrida trabaja el servicio. `404` si no existe, `409` si `loaded_data` es false. `activated_by` es **declarado** por quien llama. |
| `GET /config` | Proveedores, modelos, agentes, flujo. Sin claves. |
| `PUT /config/agents/{agent_key}` | Override. |
| `DELETE /config/agents/{agent_key}` | Reset. |
| `POST /config/agents/{agent_key}/profiles` | Alta de perfil. |
| `PUT /config/agents/{agent_key}/profiles/{profile_id}` | Edición. |
| `DELETE /config/agents/{agent_key}/profiles/{profile_id}` | Baja. |
| `PUT /config/providers/{provider_id}` | Metadatos. |
| `PUT /config/providers/{provider_id}/key` | Clave write-only. |
| `DELETE /config/providers/{provider_id}/key` | Borra la clave guardada. |
| `POST /config/providers/{provider_id}/models` | Alta de modelo. |
| `PUT /config/providers/{provider_id}/models/{model}` | Edición. |
| `DELETE /config/providers/{provider_id}/models/{model}` | 204. |
| `POST /config/providers/{provider_id}/models/refresh` | Refresh del catálogo. |

## Notas

- **Auth sí; multi-tenant no.** La consola autentica personas (Auth.js,
  dos roles) y el servicio pide un token compartido que agrega el cliente
  base. Lo que sigue sin existir es el tenant por usuario: es un setting del
  despliegue. No agregar `/org/[slug]/` ni una columna `tenant_id` hasta que
  haya capability detrás.
- **Todo lo que no esté en `(auth)/` exige sesión.** Una página nueva
  colgada de `app/` y no de `app/(console)/` queda publicada sin gate. El
  `matcher` de `proxy.ts` enumera lo que se alcanza sin cookie: `/api/auth/*`,
  `/login`, `/register`, los assets de Next y `/brand/*`.
- **El browser nunca ve `AI_SERVICE_URL`.** Privada, sin prefijo
  `NEXT_PUBLIC_`. `lib/ai-service/base-client.ts` importa `server-only`.
- **Una pantalla, un módulo de nav.** Si se agrega una página, se agrega
  el ítem en `CONSOLE_MODULES` y la fila en esta tabla en el mismo change.
- **Dónde corre cada capa.** Las páginas y Route Handlers de esta lista
  se despliegan en **Vercel** (`business-backend/`). Los paths de
  “API del servicio IA” se despliegan en **Railway** (`ai-service/`).
  El browser solo alcanza Vercel.

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

La nav y la portada leen `lib/console-nav.ts`. Una pantalla nueva que no
esté en `CONSOLE_MODULES` no aparece en el sidebar ni en el home.

| Path | Propósito |
|---|---|
| `layout.tsx` | Layout raíz: script de tema en `<head>`, sidebar, header. `lang="es"`. Sin `className` en `<html>` — React lo resetearía al hidratar y borraría `dark`. |
| `page.tsx` | Portada agrupada por los tres módulos del operador (Respuesta, RAG, Configuración). Sin métricas en vivo: `p@10` y los conteos salen de scripts, no de un endpoint. |
| `answer/page.tsx` | Chat agentico. Server Component: carga facets y perfiles del sintetizador; el hilo vive en `answer-console.tsx`. No usa `PageFrame`: el thread ocupa el inset entero. |
| `search/page.tsx` | Búsqueda híbrida con procedencia. Server Component precarga facets; falla de facets → lista vacía, no error page. |
| `documents/page.tsx` | Vista previa de chunking. **No persiste.** El corpus se construye en `/corpus`. |
| `corpus/page.tsx` | Rebuild (trocear, embeber, cargar) y seguimiento del job. Server Component lee identidad del corpus y jobs recientes para el guard de `reset`. |
| `agents/page.tsx` | Catálogo de agentes desde `GET /config`. Persona, guardrails, tools. `dynamic = "force-dynamic"`. Degrada a catálogo vacío si el servicio no responde. |
| `agents/flow/page.tsx` | Diagrama del grafo que corre `POST /answer/agentic`. Crear un perfil no agrega un nodo. |
| `models/page.tsx` | Proveedores, catálogo de modelos, credenciales write-only. Un proveedor sin clave usable se deshabilita en la UI. |

## Layouts y shell

| Path | Propósito |
|---|---|
| `layout.tsx` | Único layout. No hay grupo `(public)` / `(private)`: la consola no tiene auth todavía. |
| `components/app-sidebar.tsx` | Sidebar; lee `CONSOLE_MODULES`. |
| `components/app-header.tsx` | Header con conmutador de tema. |
| `components/page-frame.tsx` | Columna con padding para pantallas-herramienta. El chat no la usa. |

## Route Handlers (BFF)

El browser solo habla con estas rutas. Cada una reenvía a `ai-service`
vía `lib/ai-service/`. No re-declarar defaults ni validación de negocio
que ya vive en el servicio; el BFF solo rechaza lo que no puede
reenviar (JSON inválido, `q` ausente, archivo ausente).

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
| `api/answer/sessions/route.ts` | `GET` — lista de conversaciones no vacías del tenant. Reenvía `limit`/`offset` si vienen; un `[]` es éxito. |
| `api/answer/session/[sessionId]/route.ts` | `GET` memoria + transcript (`history`, `title`, timestamps); `PATCH` renombra; `DELETE` la descarta (204, idempotente). |
| `api/answer/session/[sessionId]/anchors/[kind]/[value]/route.ts` | `DELETE` — quita un anchor. |

No hay Route Handler para `POST /answer` (un solo tiro). Ese camino lo
usa el eval del servicio, no la consola.

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
| `POST /answer` | Un tiro: retrieve → generate. Rechaza `session_id` con 422. |
| `POST /answer/agentic` | Grafo LangGraph. 200 o 202 (gate humano). |
| `POST /answer/agentic/start` | Igual, en background, para progreso en vivo. |
| `POST /answer/agentic/resume` | Retoma un thread. |
| `GET /answer/agentic/{thread_id}/progress` | Eventos de nodos. |
| `POST /answer/session` | Emite `session_id`. |
| `GET /answer/sessions` | Lista resúmenes del tenant (`title`, `turn_count`, timestamps). Sin vacías ni vencidas. Paginado `limit`/`offset`. |
| `GET /answer/session/{session_id}` | Memoria (hechos, anchors, ventana) más `title`, `history` y timestamps. |
| `PATCH /answer/session/{session_id}` | Renombra. 422 si el título queda vacío. |
| `DELETE /answer/session/{session_id}` | 204 idempotente. |
| `DELETE /answer/session/{session_id}/anchors/{kind}/{value}` | Quita un anchor. |
| `POST /corpus/rebuild` | 202 + job id. La raíz del corpus sale de settings, no del body. |
| `GET /corpus/jobs` | Lista. |
| `GET /corpus/jobs/{job_id}` | Detalle. |
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

- **Sin auth / multi-tenant en la UI.** El servicio no tiene usuarios ni
  token. No agregar `/sign-in` ni `/org/[slug]/` hasta que exista
  capability detrás.
- **El browser nunca ve `AI_SERVICE_URL`.** Privada, sin prefijo
  `NEXT_PUBLIC_`. `lib/ai-service/base-client.ts` importa `server-only`.
- **Una pantalla, un módulo de nav.** Si se agrega una página, se agrega
  el ítem en `CONSOLE_MODULES` y la fila en esta tabla en el mismo change.
- **Dónde corre cada capa.** Las páginas y Route Handlers de esta lista
  se despliegan en **Vercel** (`business-backend/`). Los paths de
  “API del servicio IA” se despliegan en **Railway** (`ai-service/`).
  El browser solo alcanza Vercel.

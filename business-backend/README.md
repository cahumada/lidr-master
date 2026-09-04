# Visual Time RAG — consola web

El frontend y el backend de negocio: Next.js (App Router, TypeScript),
Tailwind y componentes [shadcn/ui](https://ui.shadcn.com). Uno de los dos
proyectos del repo; el otro es [`ai-service/`](../ai-service/README.md).
Portada del monorepo en el [README de la raíz](../README.md).

## Puesta en marcha

```bash
cd business-backend
pnpm install
cp .env.example .env.local     # AI_SERVICE_URL apuntando a tu servicio
pnpm dev
```

Necesita el servicio IA corriendo:

```bash
cd ../ai-service && uv run uvicorn app.main:app --reload
```

## El browser nunca habla con el servicio IA

Toda llamada al servicio sale **del servidor de Next**, desde los Route
Handlers de `app/api/`. El browser solo habla con el origen de esta app.

Eso no es una preferencia de estilo: conserva, sobre Vercel + Railway, la
misma propiedad que el `docker-compose` del curso obtiene teniendo un solo
servicio con puertos publicados. `AI_SERVICE_URL` es privada —sin prefijo
`NEXT_PUBLIC_`— y el servicio IA hoy no tiene autenticación, así que su URL
sería la única barrera si el browser le hablara directo.

`lib/ai-service/base-client.ts` importa `server-only`: intentar usarlo desde un
Client Component es un error de build, no un descuido que se descubre en
producción.

## Estructura

```
app/
├── api/                       # Route Handlers: el proxy hacia el servicio IA
│   ├── search/
│   ├── answer/agentic/ · answer/agentic/resume/
│   ├── answer/agentic/start/ · answer/agentic/[threadId]/progress/
│   ├── config/ · config/agents/[agentKey]/
│   ├── documents/ingest-file/
│   └── corpus/rebuild · jobs · jobs/[id]
├── search/                    # Búsqueda: la pantalla principal
├── answer/                    # Respuesta agentica: formulario, traza y gate humano
├── agents/                    # Catálogo de agentes y sus perfiles (persona, modelo)
├── documents/                 # Vista previa de ingesta (no persiste)
└── corpus/                    # Reconstrucción del corpus y sus trabajos
lib/ai-service/                # LA ÚNICA capa que habla HTTP con el servicio
├── base-client.ts             # fetch, timeouts, y los errores del servicio
├── types.ts                   # espejo 1:1 de los schemas Pydantic
├── search.ts · documents.ts · corpus.ts · answer.ts · config.ts   # un cliente por contexto
components/ui/                 # shadcn: el código vive acá, no en node_modules
```

### Respuesta agentica (`app/answer/`)

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

### Agentes (`app/agents/`)

Arma toda la pantalla desde `GET /config`: el rol de cada agente, sus
herramientas permitidas y su modelo vigente salen del servicio que corre el
grafo, no de una copia declarada acá — la consola no puede describir un grafo
que ya no existe.

Arriba, un panel de **proveedores** (`app/agents/providers-panel.tsx`)
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
pnpm dev      # desarrollo
pnpm lint     # eslint
pnpm build    # build de producción; corre TypeScript
pnpm start    # servir el build
```

## Despliegue

Vercel, con **root directory `business-backend/`** y `AI_SERVICE_URL` apuntando
a la URL pública del servicio IA en Railway. El detalle —y el filtro de rutas
para que un commit del servicio no dispare un build acá— está en el
[README de la raíz](../README.md).

# Visual Time RAG — consola web

El frontend y el backend de negocio: Next.js (App Router, TypeScript),
Tailwind y componentes [shadcn/ui](https://ui.shadcn.com). Uno de los dos
proyectos del repo; el otro es [`ai-service/`](../ai-service/README.md).
Portada del monorepo en el [README de la raíz](../README.md).

## Puesta en marcha

```bash
cd business-backend
npm install
cp .env.example .env.local     # AI_SERVICE_URL apuntando a tu servicio
npm run dev
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
│   ├── documents/ingest-file/
│   └── corpus/rebuild · jobs · jobs/[id]
├── search/                    # Búsqueda: la pantalla principal
├── documents/                 # Vista previa de ingesta (no persiste)
└── corpus/                    # Reconstrucción del corpus y sus trabajos
lib/ai-service/                # LA ÚNICA capa que habla HTTP con el servicio
├── base-client.ts             # fetch, timeouts, y los errores del servicio
├── types.ts                   # espejo 1:1 de los schemas Pydantic
├── search.ts · documents.ts · corpus.ts   # un cliente por contexto
components/ui/                 # shadcn: el código vive acá, no en node_modules
```

Los contextos (`search`, `documents`, `corpus`) **no se importan entre sí**, y
ninguna pantalla hace `fetch` al servicio por su cuenta: si falta una llamada,
se agrega al cliente del contexto que corresponde.

`types.ts` espeja los schemas de `ai-service/app/generation/rag/schemas.py` y
`ai-service/app/ingestion/schemas.py`. Cuando el servicio agrega un campo, se
agrega ahí **primero** — una pantalla no lee un campo que ese archivo no
declara.

## Comandos

```bash
npm run dev     # desarrollo
npm run lint    # eslint
npm run build   # build de producción; corre TypeScript
npm start       # servir el build
```

## Despliegue

Vercel, con **root directory `business-backend/`** y `AI_SERVICE_URL` apuntando
a la URL pública del servicio IA en Railway. El detalle —y el filtro de rutas
para que un commit del servicio no dispare un build acá— está en el
[README de la raíz](../README.md).

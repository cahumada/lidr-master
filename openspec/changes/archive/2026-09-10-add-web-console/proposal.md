## Why

El repo tiene un pipeline completo (ingesta, chunking, embeddings, pgvector,
recuperación híbrida con RRF, reranker) pero **ningún endpoint tiene una
interfaz que no sea Swagger o `curl`**. El proyecto final del Master pide la
interfaz, y el programa la ubica en `business-backend/`: el frontend y el
backend de negocio, el único de los dos proyectos que habla con el humano.

El `CLAUDE.md` de `session_16` describe la implementación Rails de ese
directorio como la de referencia y deja explícito que **cada estudiante puede
usar otra stack**. Acá se usa Next.js, con Tailwind y componentes shadcn/ui,
desplegado en Vercel; el servicio IA se despliega en Railway.

Lo que **no** se copia del curso son sus pantallas. Su `business-backend/`
expone estimación conversacional, laboratorio de chunking, corridas de agentes
con gates humanos y una bandeja de supervisión — todo eso existe porque su
servicio IA genera respuestas con un LLM orquestado. Acá la capa de generación
está declarada como no construida (`openspec/project.md`, "Estado y alcance").
Construir esas pantallas sería documentar una capability inexistente, que es
exactamente lo que `AGENTS.md` §3 prohíbe.

Este change depende de
[`move-service-to-ai-service`](../move-service-to-ai-service/proposal.md), que
lleva el servicio a `ai-service/` y libera el lugar donde va esta app.

## What Changes

- Nueva app **`business-backend/`**: Next.js (App Router, TypeScript),
  Tailwind y componentes **shadcn/ui** copiados al repo (no una dependencia de
  librería de componentes). Dependencias con **`pnpm`**, fijado en
  `packageManager` y con `pnpm-lock.yaml` como único lockfile: CI instala con
  `--frozen-lockfile`, la contraparte exacta del `uv sync --frozen` del
  servicio.
- **Tema claro y oscuro**, tomado literal del registry item de un tema de
  tweakcn (`Woken`) en vez de escribir tokens a mano, con un conmutador en la
  barra y la elección persistida. Se resuelve **sin `next-themes`**: la
  mecánica —una clase en `<html>`, un script inline, `localStorage`— son unas
  pocas decenas de líneas en `lib/theme.ts`, y agregar una dependencia para eso
  no se sostiene contra `AGENTS.md` §3.
- Nueva capability `web-console`: tres pantallas, una por grupo de endpoints
  que el servicio IA expone hoy — búsqueda (`GET /search`), vista previa de
  ingesta (`POST /documents/ingest[-file]`) y reconstrucción de corpus
  (`POST /corpus/rebuild` + `GET /corpus/jobs[/{id}]`).
- **Una sola capa habla HTTP con el servicio IA**: `lib/ai-service/`, con un
  cliente base más un cliente por contexto (`search`, `documents`, `corpus`).
  Es la traducción directa de la convención del curso (`app/services/estimator_ai/`:
  `BaseClient` + un cliente por contexto, la única capa que habla HTTP con
  FastAPI, y contextos que nunca se importan entre sí).
- **Tipos TypeScript que espejan los schemas Pydantic 1:1**, como los POROs del
  curso espejan los suyos (`from_hash` ↔ `model_validate`). Las vistas
  renderizan objetos tipados, nunca JSON crudo.
- Las llamadas al servicio IA salen **solo del servidor** (Route Handlers).
  El browser habla únicamente con el origen de Next.js.
- `.github/workflows/ci.yml`: un job por proyecto, cada uno condicionado a si
  sus rutas cambiaron (`dorny/paths-filter`, igual que el curso). **Ningún job
  despliega**: eso lo hace la integración nativa de cada plataforma con GitHub.
- `ai-service/Dockerfile` (hoy no existe ninguno), condición para desplegar en
  Railway.

**Deliberadamente afuera:**

- **Vercel AI SDK.** El pedido lo condiciona a "si es necesario", y hoy no lo
  es: no hay endpoint de generación que streamear. Entra cuando exista, y
  entra apuntado al Route Handler propio — nunca a un proveedor de modelos.
  Ver `design.md`.
- **Dashboard de evaluación y visor del mapa de procesos.** Ninguno de los dos
  tiene endpoint HTTP: viven en `scripts/eval_retrieval.py` y
  `scripts/build_process_map.py`. Agregar uno para alimentar una pantalla es
  construir capability de servicio dentro de un change de interfaz. Son su
  propio `proposal.md`.
- **Autenticación y multi-tenant en la UI.** El servicio no tiene ni token ni
  usuarios; el selector de tenant sería una pantalla sin nada detrás.

## Capabilities

### New Capabilities
- `web-console`: interfaz web para ejecutar búsqueda, vista previa de ingesta y
  reconstrucción de corpus sin Swagger ni terminal, con la procedencia de cada
  resultado a la vista.

### Modified Capabilities
(ninguna — el servicio IA no cambia. El patrón de proxy server-side evita
incluso tener que habilitarle CORS; ver `design.md`.)

## Impact

- Archivos nuevos: `business-backend/**`, `ai-service/Dockerfile`,
  `ai-service/.dockerignore`, `.github/workflows/ci.yml`.
- Se actualizan: `openspec/project.md` (stack y convenciones de la app web),
  `README.md` de la raíz, `AGENTS.md` §4 (comandos de la app web).
- Cero cambios en `ai-service/app/`, `scripts/`, `tests/`, ni en ninguna spec
  existente.
- Configuración fuera del repo: proyecto Railway (root `ai-service/`) y
  proyecto Vercel (root `business-backend/`), documentada en `tasks.md`.

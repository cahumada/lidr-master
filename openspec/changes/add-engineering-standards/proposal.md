## Why

El repo ya tiene una fuente de verdad para **qué hace el sistema**
(`openspec/specs/`) y para **el sistema fuente** (`openspec/domain/`). Lo que
faltaba era un lugar para **cómo se escribe y se opera el código**: convenciones
de lenguaje, arquitectura de cada stack, flujo de git y el inventario de
rutas que no se pueden borrar por accidente.

Esa guía vivía mezclada en `openspec/project.md` (stack y layout) y en
`AGENTS.md` (ciclo de trabajo). Al crecer la consola y el BFF, un solo
archivo no alcanza: un agente que toca `ai-service/` no necesita las reglas
de shadcn, y uno que toca una pantalla no necesita Alembic. Sin documentos
separados, las convenciones se re-inventan o se copian de otro proyecto.

Este change no altera comportamiento de runtime. Escribe las convenciones
**después** de verificarlas contra el código — no las antedata.

## What Changes

- Nueva clase de documento `openspec/standards/`: convenciones de ingeniería,
  normativas sobre **cómo** se trabaja, no sobre **qué** hace el sistema hoy.
- Seis documentos:
  - `base-standards.md` — principios, idioma, herramientas, dónde está cada
    estándar específico.
  - `ai-service-standards.md` — FastAPI, Pydantic, DI, tests, seguridad del
    servicio Python.
  - `bff-standards.md` — Route Handlers de Next.js que hablan con el
    servicio IA.
  - `frontend-standards.md` — App Router, React, Tailwind, shadcn, tema.
  - `git-workflow.md` — git local, ramas por stack, PRs.
  - `app-routes.md` — inventario de páginas y Route Handlers que no se
    borran sin pedido explícito.
- `AGENTS.md` y `openspec/AGENTS.md` nombran la carpeta. `openspec/project.md`
  apunta a estos documentos en vez de seguir creciendo.
- Punteros finos en `.cursor/rules/` para que el harness cargue el estándar
  que corresponde al glob, sin copiar el contenido.
- Playbooks en `openspec/commands/`: `plan-ai-service`, `plan-web`,
  `develop-ai-service`, `develop-web`, `update-docs`, `commit`,
  `create-pr`. El plan **es** el change OpenSpec (`proposal.md` +
  `tasks.md` + deltas); no se escribe un plan paralelo. Punteros en
  cada harness: `.cursor/commands/`, `.claude/commands/`,
  `.opencode/commands/`, `.github/prompts/`, `.gemini/commands/`.

**Deliberadamente afuera:**

- No se convierten en capabilities de `openspec/specs/`. Una spec afirma
  comportamiento de runtime; estas reglas afirman cómo se escribe código.
- No se inventan tests de frontend, i18n, auth ni umbrales de coverage que
  el repo no tiene.
- No se agregan dependencias ni se cambia código de producto.

## Capabilities

### New Capabilities

(ninguna — este change no mueve comportamiento de runtime)

### Modified Capabilities

(ninguna)

## Impact

- Archivos nuevos: `openspec/standards/*.md`, `openspec/commands/*.md`,
  `openspec/changes/add-engineering-standards/**`, `.cursor/rules/*.mdc`,
  punteros de comando en `.cursor/commands/`, `.claude/commands/`,
  `.opencode/commands/`, `.github/prompts/`, `.gemini/commands/`,
  más `GEMINI.md` y `.github/copilot-instructions.md`.
- Se actualizan: `AGENTS.md`, `openspec/AGENTS.md`, `openspec/project.md`.
- Cero cambios en `ai-service/app/`, `business-backend/app/`, tests o CI.

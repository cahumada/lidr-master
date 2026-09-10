# Implementation Tasks

## 1. Documentos de estándares

- [x] 1.1 Crear `openspec/standards/base-standards.md` adaptado a este monorepo.
- [x] 1.2 Crear `openspec/standards/ai-service-standards.md` para el servicio Python.
- [x] 1.3 Crear `openspec/standards/bff-standards.md` para los Route Handlers de Next.
- [x] 1.4 Crear `openspec/standards/frontend-standards.md` para la consola Next.
- [x] 1.5 Crear `openspec/standards/git-workflow.md` (backend = ai-service, frontend = Next completo).
- [x] 1.6 Crear `openspec/standards/app-routes.md` con las páginas y APIs verificadas contra el código.

## 2. Punteros y ciclo de trabajo

- [x] 2.1 Actualizar `AGENTS.md` para nombrar `openspec/standards/` y `commands/`.
- [x] 2.2 Actualizar `openspec/AGENTS.md` con las clases standards y commands.
- [x] 2.3 Actualizar `openspec/project.md` para apuntar a los estándares.
- [x] 2.4 Agregar punteros finos en `.cursor/rules/` (sin copiar el contenido).
- [x] 2.5 Playbooks en `openspec/commands/` + punteros en Cursor, Claude, OpenCode, Copilot y Gemini.

## 3. Verificar

- [x] 3.1 `python scripts/validate_specs.py` pasa (el warning de “sin deltas” es esperado).
- [x] 3.2 Ningún documento menciona el proyecto de origen ni rutas ajenas a este repo.
- [x] 3.3 Despliegue explícito: `ai-service/` → Railway, `business-backend/` → Vercel.

# Design: dónde viven las convenciones de ingeniería

## El problema de ubicación

Hay tres lugares tentadores y los tres están mal para este contenido:

1. **`openspec/specs/`** — una capability afirma qué hace el sistema *hoy*.
   “Los identificadores van en inglés” no es un comportamiento observable
   del RAG. Meterlo como `### Requirement:` mezclaría process con producto
   y el validador exigiría escenarios WHEN/THEN para reglas de estilo.
2. **`openspec/project.md`** — ya es el mapa del stack. Si absorbiera
   testing, SOLID, inventario de rutas y el flujo de git, dejaría de ser
   un mapa y pasaría a ser un manual que nadie lee entero.
3. **`.cursor/rules/*.mdc` con el texto completo** — `AGENTS.md` §5 lo
   prohíbe: el harness es un puntero. Dos copias se desincronizan.

## La decisión

Una cuarta clase de documento, `openspec/standards/`:

| Carpeta | Describe | Normativo sobre |
|---|---|---|
| `openspec/specs/` | qué hace **nuestro** sistema hoy | el código de producto |
| `openspec/domain/` | el sistema **fuente** (VisualTIME) | nada — es referencia |
| `openspec/changes/` | trabajo propuesto o en curso | nada hasta archivarse |
| `openspec/standards/` | **cómo** se escribe y se opera el código | agentes y personas |

El validador no recorre `standards/`: no hay Requirement/Scenario que
chequear. La autoridad es humana — si el código y el estándar discrepan,
se actualiza el estándar en el mismo change que cambia la convención, o
se corrige el código.

## Por qué dos documentos de “backend”

El monorepo tiene dos backends de verdad:

- **`ai-service/`** es la API de producto: FastAPI, Pydantic, pgvector, LLM.
- **`business-backend/app/api/`** es un BFF: Route Handlers que reenvían
  al servicio. No hay Prisma, no hay dominio propio, no hay jobs.

Un solo “backend-standards” los mezclaría. Quien toca un router de FastAPI
no necesita saber `toErrorPayload`; quien toca un Route Handler no necesita
saber Alembic. Por eso `ai-service-standards.md` y `bff-standards.md`.

El frontend (`frontend-standards.md`) cubre páginas, componentes y tema.
El BFF no vive ahí: es servidor, aunque esté en el mismo paquete Next.

## Ramas

El trabajo en paralelo se separa por stack, no por “capa imaginaria”:

- sufijo `-ai-service` — cambios en el servicio Python
- sufijo `-web` — cambios en Next completo (páginas **y** BFF)

Un change que toca los dos (contrato nuevo + pantalla) puede ir en una
sola rama `-web` si el delta del servicio es el espejo del tipo
TypeScript, o en dos PRs si el contrato tiene que aterrizar primero.

## Comandos: el plan es el change

Los playbooks de “plan ticket / develop / commit / PR” no escriben un
markdown paralelo (`*_backend.md`). En este repo **qué se quiere
hacer** es `proposal.md` y **cómo implementarlo** es `tasks.md`.
`plan-ai-service` y `plan-web` crean esa carpeta; `develop-*` la
recorre; `update-docs` alinea specs; `commit` y `create-pr` mueven
el git. Jira es opcional y solo si el argumento es un ticket.

Cada harness tiene punteros, no una copia: `.cursor/commands/`,
`.claude/commands/`, `.opencode/commands/`, `.github/prompts/`,
`.gemini/commands/`. Un modelo que solo lea `AGENTS.md` (Codex,
OpenCode, etc.) entra por `openspec/commands/README.md`. OpenCode
además carga `AGENTS.md` solo y los slash commands desde
`.opencode/commands/`.

## Alternativas descartadas

- **Copiar el formato `.mdc` alwaysApply con globs del otro repo.** El
  contenido quedaría atado a un harness. Acá el texto canónico es
  markdown en `openspec/`; el `.mdc` solo apunta.
- **Capability `engineering-standards` con escenarios.** Sería tautológica
  (“WHEN un agente escribe código THEN sigue los estándares”) y no
  describiría el sistema.
- **Un solo `conventions.md`.** El documento de frontend del proyecto de
  referencia tiene miles de líneas de producto ajeno. Separar por
  audiencia es lo que hace que se lean.

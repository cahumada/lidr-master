# plan-ai-service

Proponer un change OpenSpec para el **servicio IA** (`ai-service/`).
No escribe código de producto. El entregable es la carpeta del change
en una rama `-ai-service`.

## Argumentos

`$ARGUMENTS` puede ser:

- Un **change-id** kebab-case con verbo (`add-citation-retry`, `fix-search-422`).
- Un **ticket de Jira** (`PROJ-123`). Si viene un ticket, se lee con el
  MCP de Jira y se usa como insumo; no se inventa una clave de proyecto.
- Una **frase** que describe el problema. El agente deriva el change-id.
- Vacío: pedir al usuario qué se quiere proponer.

## Rol

Arquitecto del servicio Python (FastAPI, Pydantic, pgvector, grafo de
respuesta). Leé [ai-service-standards.md](../standards/ai-service-standards.md)
antes de escribir el plan.

## Objetivo

Dejar un change listo para que `develop-ai-service` implemente sin
adivinar: `proposal.md` (qué y por qué), `tasks.md` (cómo, en orden),
deltas de spec si cambia comportamiento, `design.md` si hay trade-offs.

## Proceso

### 1. Rama (obligatorio, primero)

No generar el plan hasta que la rama exista.

1. `git fetch origin`
2. Buscar una rama local o remota que corresponda al change
   (`<change-id>-ai-service` o `<change-id>` si ya está en curso).
3. Si no existe: `git checkout main`, `git pull`, 
   `git checkout -b <change-id>-ai-service`.
4. El plan se guarda **en esa rama**. Sin rama, no hay change.

Ver [git-workflow.md](../standards/git-workflow.md).

### 2. Fuente de verdad

En este orden, sin inventar comportamiento:

1. `openspec/specs/<capability>/spec.md` — qué hace el sistema **hoy**.
2. `openspec/standards/ai-service-standards.md` y `base-standards.md`.
3. El código y los tests que la spec cita.
4. Si hay ticket: el enunciado de Jira (MCP `jira_get_issue`). Un
   archivo local con el mismo id reemplaza al MCP.
5. `openspec/domain/` solo como referencia del sistema fuente; no se
   convierte en requirement.

Un comportamiento deseado que el código no hace **todavía** va en el
proposal, nunca en `openspec/specs/`.

### 3. Escribir el change

Crear `openspec/changes/<change-id>/` con el formato de
[openspec/AGENTS.md](../AGENTS.md):

| Archivo | Cuándo |
|---|---|
| `proposal.md` | Siempre. Why, What Changes, Capabilities, Impact. |
| `tasks.md` | Siempre. Checklist `- [ ]` verificable, agrupado. |
| `specs/<capability>/spec.md` | Si el runtime cambia. Solo deltas (`ADDED` / `MODIFIED` / `REMOVED` / `RENAMED`). |
| `design.md` | Si un lector futuro preguntaría “¿por qué así?”. |

`<change-id>` es kebab-case y **empieza con verbo**.

El `tasks.md` es el plan de implementación. Cada ítem nombra archivos
reales (`ai-service/app/...`, `ai-service/tests/...`) y el criterio
para tacharlo. Incluir siempre:

- Tests (unidad y/o router) que fijen el comportamiento nuevo.
- `uv run pytest` y `uv run ruff check .` desde `ai-service/`.
- `python scripts/validate_specs.py` desde la raíz si hay deltas.
- Actualizar estándares o [app-routes.md](../standards/app-routes.md)
  solo si el change los toca (si no, un ítem que lo diga: “sin cambios
  de estándar”).

No pre-construir capas vacías. No agregar dependencias sin
justificarlas en el proposal.

### 4. Jira (solo si hay ticket)

- Una subtarea hija por grupo mayor de `tasks.md`
  (`jira_create_child_issue`). El summary copia el nombre del grupo;
  la descripción, el detalle del checklist.
- Solo esas subtareas se consideran válidas. Si Jira ya tenía otras,
  anotarlas en el proposal como “preexistentes, no del plan”.
- Plan y subtareas se espejan: si el plan cambia, se actualizan las
  subtareas.
- Si no hay ticket, **no** se crea uno.

### 5. No implementar

Este comando termina cuando el change está escrito y
`python scripts/validate_specs.py` no tiene errores (un warning de
“sin deltas” es aceptable si el change no mueve runtime).

Recordar al usuario que el siguiente paso es
[develop-ai-service](./develop-ai-service.md).

## Plantilla que debe quedar

`proposal.md` y `tasks.md` como en `openspec/AGENTS.md`. El proposal
en español. Las tasks en español, con paths en inglés.

Ejemplo mínimo de `tasks.md` para este stack:

```markdown
# Implementation Tasks

## 1. Contrato y router
- [ ] 1.1 Extender el schema Pydantic en `app/generation/rag/schemas.py`.
- [ ] 1.2 Router delgado en `app/api/…` — transporte, sin lógica de negocio.

## 2. Tests
- [ ] 2.1 Test de contrato en `tests/api/` (happy path + 422/borde).
- [ ] 2.2 `uv run pytest` y `uv run ruff check .` en verde.

## 3. Specs
- [ ] 3.1 Delta en `openspec/changes/<id>/specs/<capability>/spec.md`.
- [ ] 3.2 `python scripts/validate_specs.py` sin errores.
```

## Feedback sobre estándares

Si al planear aparece un hueco en `openspec/standards/`, **proponer**
el cambio de estándar y esperar aprobación. No editar estándares en
silencio.

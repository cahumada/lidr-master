# update-docs

Actualizar la documentación **según el diff real**. No inventar
comportamiento. Una spec afirma lo que el código hace hoy; un
deseo va en un proposal.

## Argumentos

`$ARGUMENTS`: change-id, área (`ai-service`, `web`, `standards`),
o vacío (inferir del diff y de la rama).

## Objetivo

Que `openspec/` y los estándares coincidan con lo que se acaba
de implementar, y que `python scripts/validate_specs.py` pase.

## Qué se actualiza (solo lo tocado)

| Si el diff… | Actualizar |
|---|---|
| Cambia comportamiento de runtime | Deltas en `openspec/changes/<id>/specs/<capability>/spec.md`, o la spec actual si se está archivando |
| Agrega o saca una página / Route Handler / endpoint FastAPI | [app-routes.md](../standards/app-routes.md) |
| Cambia una convención de código | El estándar del stack (`ai-service`, `bff`, `frontend`, `base`, `git-workflow`) |
| Cambia stack, layout o comandos | [project.md](../project.md) y, si aplica, [AGENTS.md](../../AGENTS.md) |
| Cambia el formato de specs/changes | [openspec/AGENTS.md](../AGENTS.md) **y** `scripts/validate_specs.py` juntos |
| Agrega conocimiento del sistema fuente | `openspec/domain/<tema>.md` con estado de evidencia |

No crear una capability nueva “de documentación”. No copiar
estándares a los archivos del harness (`.cursor/rules/`,
`.claude/`, `.opencode/`, prompts de Copilot, …) — esos archivos
son punteros.

## Proceso

1. `git status` + `git diff` (y el `proposal.md` / `tasks.md` del
   change). Listar qué cambió de verdad.
2. Para cada capability tocada: leer la spec actual, el código y
   un test. Escribir solo lo verificado. SHALL + al menos un
   escenario `WHEN` / `THEN` en los deltas.
3. Tachar en `tasks.md` los ítems de documentación que este
   comando completa.
4. `python scripts/validate_specs.py` desde la raíz. Corregir
   errores de formato antes de dar por cerrado.
5. **No archivar** salvo que el usuario pida cerrar el change:
   plegar deltas en `openspec/specs/` y mover la carpeta a
   `openspec/changes/archive/<YYYY-MM-DD>-<change-id>/`.
6. No commitear acá. Recordar [commit](./commit.md).

## Idioma

- Process / proposal / tasks / standards: **español**.
- Specs de capability: el idioma que ya usa esa spec; no mezclar
  en el mismo requirement.
- Código citado: inglés.

## Lo que este comando no hace

- No “mejora” prosa que no esté desactualizada.
- No documenta trabajo no mergeado como si ya fuera verdad actual
  (`openspec/specs/` es *hoy*; el change en vuelo es *propuesto*).
- No toca `domain/` sin etiqueta de evidencia.
- No agrega dependencias ni cambia código de producto, salvo
  comentarios/`Field(description=)` que la spec exija.

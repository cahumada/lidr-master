# develop-ai-service

Implementar un change OpenSpec en el **servicio IA**. El plan ya existe:
este comando recorre `tasks.md` en orden, tacha, verifica. No crea el PR.

## Argumentos

`$ARGUMENTS`:

- Un **change-id** (`add-citation-retry`).
- Un **ticket** que se pueda mapear a un change en vuelo.
- Vacío: usar el change de la rama actual (`openspec/changes/<id>/`
  cuyo id coincida con el prefijo de la rama).

## Rol

Ingeniero del servicio (FastAPI, tests, ruff). Estándar:
[ai-service-standards.md](../standards/ai-service-standards.md).

## Objetivo

Dejar el checklist del change en verde para el stack `ai-service/`,
sin adelantarse a tareas de `-web`.

## Proceso

### 1. Verificar que el change existe

1. Rama actual: debe ser `<change-id>-ai-service` o `<change-id>`.
   Si no hay rama, **parar** y pedir que corran
   [plan-ai-service](./plan-ai-service.md).
2. Debe existir `openspec/changes/<change-id>/proposal.md` y
   `tasks.md`. Si faltan, el plan no se hizo: no inventar el
   checklist sobre la marcha.
3. Leé el proposal, las tasks y los deltas **antes** de tocar
   código. Leé la spec actual de cada capability que el delta mueve.

### 2. Implementar

- Un ítem de `tasks.md` a la vez, en orden. Tachar al completar.
- Routers delgados. Contratos Pydantic, no `dict`. Comentarios
  `EN || ES`. Identificadores en inglés.
- Tests junto al comportamiento: `tests/` espeja `app/`. Happy path,
  422/borde, y 202/409 si el endpoint los usa.
- No borrar routers ni archivos de la app publicada salvo pedido
  explícito.
- No tragarse pérdida de negocio (cero chunks, parseo silencioso).
- Dependencia nueva: solo si el proposal la justificó.

Si una task es de consola (`business-backend/`), no la implementes
acá — pertenece a [develop-web](./develop-web.md).

### 3. Verificar

Desde `ai-service/`:

```bash
uv run pytest
uv run ruff check .
```

Desde la raíz, si hubo deltas:

```bash
python scripts/validate_specs.py
```

Un change no está listo con un check en rojo. No archivar acá:
archivar es el cierre del change, después del merge, con
[update-docs](./update-docs.md) si hace falta plegar deltas.

### 4. Git

Git **local** (`git add` / `commit` / `push`) solo si el usuario
pidió commitear, o si a continuación se corre [commit](./commit.md).
Este comando **no** abre el PR. Recordar [create-pr](./create-pr.md).

### 5. Jira (solo si el plan creó subtareas y ya existe el PR)

No transicionar Jira antes de tener la URL del PR.

- Solo las subtareas **de este plan** (servicio). No la historia
  padre si todavía hay trabajo `-web`.
- Comentario en la historia con el enlace del PR.
- Si no hay ticket, no hay nada que actualizar.

## Feedback sobre estándares

Si la implementación enseña una convención que el estándar no
dice:

1. Entender el feedback.
2. Proponer el parche concreto a `openspec/standards/…`.
3. **Esperar aprobación** antes de editar el estándar.
4. Aplicar solo lo acordado.

## Siguiente paso

[update-docs](./update-docs.md) si el diff dejó specs o estándares
desactualizados, después [commit](./commit.md) y
[create-pr](./create-pr.md).

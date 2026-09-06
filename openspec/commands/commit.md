# commit

Un commit descriptivo y, por defecto, push de la rama. **No** crea
el Pull Request: eso es [create-pr](./create-pr.md).

Git **local** (`git add`, `git commit`, `git push`). Mensajes en
inglés, conventional commits. Detalle:
[git-workflow.md](../standards/git-workflow.md).

## Argumentos

`$ARGUMENTS` puede ser:

- **Vacío**: stagear y commitear todos los cambios relevantes del
  working tree (excepto secretos y artefactos), y pushear.
- **Change-id o etiqueta**: stagear **solo** lo que pertenece a
  ese change (por path o por el id en la rama). El resto queda
  unstaged.
- **Solo el mensaje**: si el usuario dice “only commit”, “just the
  message”, “dry run”, “don't touch git” o “no push” en el sentido
  de no tocar el repo — no correr git. Listar qué se stagearía y
  el mensaje propuesto, y parar.

Este comando **sí** commitea cuando se invoca sin ese modo: es el
pedido explícito de crear el commit.

## Proceso

### 0. Modo solo descripción

Si pidieron no tocar git: inspeccionar, resolver alcance, escribir
el mensaje (subject + body) en un bloque copiable. Stop.

### 1. Estado

En paralelo:

- `git status`
- `git diff` y `git diff --staged`
- `git log` reciente (para calzar el estilo)
- Rama actual. Si estás en `main` con cambios de feature, crear
  la rama del change **antes** de commitear (`<id>-ai-service` o
  `<id>-web`).

### 2. Alcance

- Sin argumentos: todo lo relevante. Nunca `.env`, credenciales,
  `ai-service/data/`, ni artefactos de build (`.next/`,
  `__pycache__/`, `.venv/`).
- Con argumentos: solo los archivos/hunks de ese change. Si un
  archivo mezcla dos temas, stagear por hunks. Si nada coincide,
  no commitear y decirlo.

### 3. Mensaje

Inglés. Conventional commits. El subject dice el *por qué* en una
línea; el body, si hace falta, el detalle.

```
feat(ai-service): keep conversation facts out of the synthesizer prompt
fix(web): relay 202 from /answer/agentic as success
docs: add engineering standards under openspec/standards
```

- Scope `ai-service` o `web` cuando toca un solo proyecto.
- Scope `ai-service,web` cuando el mismo commit mueve el contrato
  y su espejo.
- Si hay ticket, puede ir al final del subject: `(PROJ-123)`.

No commitear un change con `tasks.md` en rojo que el mensaje
declare “listo”.

### 4. Commit y push

1. Stagear el alcance.
2. `git commit` con el mensaje (heredoc / `-m` con subject y body).
3. Si un hook de pre-commit modificó archivos, incluirlos en un
   commit **nuevo**, no amend, salvo que se cumplan las reglas de
   amend del repo (commit tuyo, no pusheado, usuario lo pidió).
4. `git push` / `git push -u origin HEAD` si la rama no trackea.
5. `git status` para confirmar.

No `--force` a `main`. No `--no-verify` salvo pedido explícito.
Si el push es rechazado, informar (pull/rebase) y no forzar.

### 5. Resumen

- Qué se commiteó (archivos y alcance).
- Si hubo argumentos: qué se dejó afuera.
- Recordar [create-pr](./create-pr.md) para abrir o actualizar el PR.

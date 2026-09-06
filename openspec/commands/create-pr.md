# create-pr

Crear o reportar el Pull Request de la rama actual. **Único**
comando que usa el MCP de GitHub. Todo lo demás (rama, commit,
push) es git local: si la rama no está pusheada, parar y pedir
[commit](./commit.md).

## Argumentos

`$ARGUMENTS` puede ser:

- **Vacío**: título y cuerpo inferidos de los commits y del
  `proposal.md` del change, si existe.
- **Change-id o ticket**: incluirlo en el título.
- **Frase**: usarla como título o como parte del cuerpo.

## MCP (obligatorio)

- Servidor: el MCP de GitHub configurado en el entorno
  (`user-github-mcp-ca`).
- Herramientas: `list_pull_requests` (o `search_pull_requests`),
  `create_pull_request`, `update_pull_request` si ya existe.
- **Repositorio:** owner `cahumada`, repo `lidr-master`.
- Si el MCP no responde, **no** caer a `gh` ni a otro MCP.
  Decirle al usuario que revise la configuración.

Descubrir el schema con la herramienta de inspección del harness
antes de invocar. No inventar parámetros.

## Proceso

### 1. Rama

`git branch --show-current`. Confirmar que trackea el remoto y
está pusheada. Base del PR: `main`.

### 2. ¿Ya hay PR?

`list_pull_requests` con:

- `owner`: `cahumada`
- `repo`: `lidr-master`
- `head`: `cahumada:<rama-actual>`
- `state`: `open`

Si existe: devolver la URL y un resumen. Actualizar el cuerpo
solo si el usuario lo pidió o si el diff creció de forma
material.

### 3. Título y cuerpo

- **Título en inglés**, misma voz que el commit principal.
- **Cuerpo**: 1–3 bullets de resumen y un test plan. Puede estar
  en español si ayuda a la review.
- Si hay `openspec/changes/<id>/proposal.md`, el resumen sale de
  Why / What Changes, no de adivinar el diff.
- Si hay ticket: `Closes PROJ-123` o `Relates to PROJ-123`.
- No crear archivos temporales (`pr_body.md`). Armar título y
  cuerpo en memoria.

### 4. Crear

`create_pull_request`:

- `owner`: `cahumada`
- `repo`: `lidr-master`
- `head`: nombre de la rama actual
- `base`: `main`
- `title` / `body` como en el paso 3

### 5. Resumen

- URL del PR.
- CI: job del proyecto que cambió + validador de specs. Ningún
  job despliega: Railway y Vercel salen del merge a `main`.
- No transicionar Jira acá; eso lo cierran los `develop-*`
  cuando ya tienen esta URL, o el usuario.

## Notas

- No force-push, no merge, no review, salvo pedido explícito.
- Este comando no commitea. Working tree sucio: advertir y no
  incluir esos archivos en el PR (el PR es lo ya pusheado).

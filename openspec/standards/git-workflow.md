# Flujo de git

Cómo se trabaja con git en este monorepo. El día a día es **git local**;
el PR es lo único que pasa por el MCP de GitHub (`create-pr`).

## Git local es el camino normal

- `git add`, `git commit` y `git push` desde la terminal o el IDE.
- El working copy y el remoto quedan en sync porque el push sale de
  *esta* máquina.
- No commitear a menos que lo pidan. No pushear a menos que lo pidan.
  No force-push a `main`.

Cuando un agente corre git, usa el repo local. No hace falta un paso
extra de “bajar lo que el agente subió”.

## Crear el PR

El PR se crea con el comando [create-pr](../commands/create-pr.md)
(MCP de GitHub), **después** de pushear la rama. Eso no toca
archivos locales. El commit y el push son
[commit](../commands/commit.md) (git local).

Antes de abrir el PR:

1. La rama está pusheada y trackea el remoto.
2. CI en verde o, si todavía corre, declarado en el cuerpo del PR.
3. El change de OpenSpec (si existe) tiene `tasks.md` al día.

## Resumen

| Situación | Acción |
|---|---|
| Desarrollo normal (commit / push) | Git local. |
| El agente commiteó o pusheó | Fue con git local; local y remoto están en sync. |
| Crear o actualizar el PR | Comando `create-pr` (MCP de GitHub), rama ya pusheada. Si el MCP no responde: título, cuerpo y URL para pegar en GitHub. |

## Ramas

`main` es la rama publicable. El trabajo sale en ramas de feature,
kebab-case, con un sufijo que dice **qué stack** se toca para poder
trabajar en paralelo sin pisarse:

| Sufijo | Qué entra | Ejemplos de paths |
|---|---|---|
| `-ai-service` | API Python | `ai-service/app/`, `ai-service/tests/`, `ai-service/alembic/` |
| `-web` | Next completo: páginas **y** BFF | `business-backend/app/`, `business-backend/components/`, `business-backend/lib/` |

El prefijo es el change-id o un resumen corto:

```
add-conversation-memory-ai-service
fix-search-facets-web
add-engineering-standards
```

Una rama **sin** sufijo vale cuando el change es de repo (OpenSpec, CI,
README) o cuando el contrato y la pantalla tienen que aterrizar juntos
y el PR único es más barato que dos. Si hay duda, dos ramas: primero
`-ai-service` (el contrato), después `-web` (el espejo TypeScript y la
UI).

Ramas chicas. Un PR que mezcla un reranker nuevo con un retoque de
padding no se reviewa.

## Commits

Conventional commits en **inglés**, como el historial del repo:

```
feat(ai-service): keep conversation facts out of the synthesizer prompt
fix(web): relay 202 from /answer/agentic as success
docs: add engineering standards under openspec/standards
```

- Scope `ai-service` o `web` cuando el commit toca un solo proyecto.
- Scope `ai-service,web` cuando el mismo commit mueve el contrato y su
  espejo.
- El cuerpo (si hace falta) explica el *por qué*, no el diff.
- No commitear `.env`, credenciales, ni nada bajo `data/` que sea del
  cliente.

## Pull requests

- Título en inglés, misma voz que el commit principal.
- Cuerpo: resumen de 1–3 bullets y un test plan. Puede estar en español
  si la review se hace en español.
- Un PR por rama. Rebase o merge según lo que pida quien reviewa; no
  force-push a `main`.
- CI (`.github/workflows/ci.yml`) corre el job del proyecto que cambió
  más el validador de specs siempre. **Ningún job despliega.**
- Tras el merge a `main`:
  - cambios en `ai-service/**` → Railway redespliega el servicio
  - cambios en `business-backend/**` → Vercel redespliega la consola
  - un commit que no toca ese root no dispara esa plataforma
    (*Watch Paths* / `ignoreCommand`). Detalle en
    [base-standards.md](./base-standards.md#6-despliegue).

## Relación con OpenSpec

Si el change altera comportamiento documentado, la rama lleva
`openspec/changes/<id>/` y no se mergea con ítems en rojo en `tasks.md`.
El flujo de git no reemplaza el ciclo proponer → implementar → verificar
→ archivar; solo dice cómo se mueve el código.

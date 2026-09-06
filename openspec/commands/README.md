# Comandos de trabajo

Playbooks para **cualquier** agente o harness: **qué se quiere hacer**
(un change OpenSpec) y **cómo implementarlo** (el checklist de ese
change). No son capabilities de producto. El validador no los recorre.

El texto canónico vive **acá**. Cada harness solo tiene un puntero.

Ciclo:

```
formalize-need  →  plan-ai-service / plan-web  →  develop-*  →  update-docs  →  commit  →  create-pr
```

`formalize-need` es opcional: si el enunciado ya alcanza para
planear, ir directo a `plan-*`.

| Comando | Hace | No hace |
|---|---|---|
| [formalize-need](./formalize-need.md) | Enuncia el *qué* en markdown (`[original]` / `[enhanced]`) | MCP, rama, change, código |
| [plan-ai-service](./plan-ai-service.md) | Rama `-ai-service` + `openspec/changes/<id>/` | Código de producto |
| [plan-web](./plan-web.md) | Rama `-web` + change para Next (páginas y BFF) | Código de producto |
| [develop-ai-service](./develop-ai-service.md) | Implementa `tasks.md` del servicio | El PR |
| [develop-web](./develop-web.md) | Implementa `tasks.md` de la consola | El PR |
| [update-docs](./update-docs.md) | Actualiza specs/standards según el diff | Código de producto, salvo docs |
| [commit](./commit.md) | Un commit + push (git local) | El PR |
| [create-pr](./create-pr.md) | Crea o reporta el PR (MCP de GitHub) | `git commit` / `git push` |

## Dónde se invoca

| Harness | Entrada del repo | Punteros de comando |
|---|---|---|
| Cualquiera (Codex, etc.) | [AGENTS.md](../../AGENTS.md) | Leé el playbook de esta carpeta |
| Cursor | `.cursor/rules/` → AGENTS.md | `.cursor/commands/<nombre>.md` |
| Claude Code | [CLAUDE.md](../../CLAUDE.md) | `.claude/commands/<nombre>.md` |
| OpenCode | [AGENTS.md](../../AGENTS.md) | `.opencode/commands/<nombre>.md` |
| GitHub Copilot | `.github/copilot-instructions.md` | `.github/prompts/<nombre>.prompt.md` |
| Gemini CLI | [GEMINI.md](../../GEMINI.md) | `.gemini/commands/<nombre>.toml` |

Un harness nuevo: el archivo que espera + un puntero a este
directorio. Nunca una copia del playbook. Detalle en
[AGENTS.md §5](../../AGENTS.md).

Fuente de verdad del formato: [openspec/AGENTS.md](../AGENTS.md).
Convenciones: [openspec/standards/](../standards/base-standards.md).

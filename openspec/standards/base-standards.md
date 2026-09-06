# Estándares básicos

Reglas que aplican a cualquier agente o persona que trabaje en este
monorepo. Los estándares por stack viven en documentos hermanos; este
archivo es el índice y las reglas que no dependen de Python ni de Next.

## 1. Principios

- **Pasos chicos, de a uno.** No avanzar más de un paso a la vez. Preferir
  cambios incrementales y enfocados antes que una modificación grande.
- **Verificar contra el código.** Una convención afirma lo que el repo
  realmente hace. Un comportamiento deseado pero no construido va en un
  `openspec/changes/<id>/proposal.md`, nunca se escribe como si ya existiera.
- **Tipado completo.** Python con anotaciones y Pydantic; TypeScript en
  modo strict. Sin `any` / `dict` pelado en un contrato expuesto.
- **Nombres claros.** Identificadores que se lean sin el comentario de al
  lado.
- **Cuestionar supuestos.** Distinguir hecho de hipótesis, sobre todo en
  `openspec/domain/` (cada afirmación lleva su estado de evidencia).
- **Detectar repetición.** Si el mismo patrón aparece dos veces, nombrarlo
  y extraerlo — o decir por qué no.
- **No borrar código que funciona.** No eliminar páginas, Route Handlers,
  routers FastAPI ni archivos que forman parte de la app publicada salvo
  que el usuario lo pida explícito. El inventario está en
  [Rutas de la consola](./app-routes.md). Ante la duda, preguntar.
- **No tragarse pérdida de negocio.** Una celda de tabla perdida, un parseo
  silencioso o un documento que produce cero chunks sin avisar es un
  defecto. Tiene que advertir, reportarse o fallar fuerte.

## 2. Idioma

- **Código en inglés.** Variables, funciones, clases, módulos, claves de
  dict, valores `Literal` que sean identificadores (`"table"`,
  `"narrative"`), mensajes de log, nombres de test.
- **Comentarios y docstrings bilingües.** Primero inglés, luego ` || `,
  luego español, en el mismo bloque. Aplica a `Field(description=...)`
  porque ese texto se publica en Swagger.
- **Excepción — datos de dominio literales.** Los headings del documento
  fuente (`"Función"`, `"Efecto"`, `"Validaciones"`) se conservan en
  español como *valor*. La *clave* que los contiene va en inglés
  (`section`).
- **Texto para una persona.** Cadenas que se renderizan en la UI van en
  español, una sola vez — no bilingües. Un usuario no lee la misma frase
  dos veces.
- **Documentación de proceso en español.** `openspec/` (project, standards,
  proposals, tasks) se escribe en español. Las specs de capability pueden
  estar en inglés o español; no mezclar los dos en el mismo requirement.
- **Commits y PRs en inglés.** Conventional commits, como el historial
  actual: `feat(ai-service): …`, `fix(web): …`. El cuerpo del PR puede
  ampliar en español si ayuda a la review.

```python
# Good
log.info("documents_ingest_done", filename=filename, total_chunks=stats.total_chunks)

# Avoid
log.info("ingesta_terminada", archivo=filename)
```

```typescript
// Good — comment bilingual, user-facing string in Spanish
/** Relay to `GET /search`. || Relay hacia `GET /search`. */
return Response.json({ error: "Falta la consulta `q`.", status: 400 }, { status: 400 })
```

## 3. Ciclo de trabajo

Para cualquier cosa más allá de un typo o un fix de una línea:

1. **Proponer** — `openspec/changes/<change-id>/` con `proposal.md`,
   `tasks.md`, deltas de spec si cambia comportamiento, y `design.md`
   cuando hay trade-offs. `<change-id>` es kebab-case y empieza con verbo.
2. **Implementar** — tachar el checklist a medida que entra.
3. **Verificar** — desde `ai-service/`: `uv run pytest` y `uv run ruff check .`.
   Desde `business-backend/`: `pnpm lint` y `pnpm build`. Desde la raíz:
   `python scripts/validate_specs.py`.
4. **Archivar** — integrar deltas en `openspec/specs/` y mover el change a
   `openspec/changes/archive/<YYYY-MM-DD>-<id>/`.

Ir directo al código solo si no se altera ningún comportamiento
documentado. Si la spec se escribe después del código, decirlo en el
proposal.

Detalle del formato: [AGENTS.md](../../AGENTS.md) y
[openspec/AGENTS.md](../AGENTS.md). Flujo de git:
[git-workflow.md](./git-workflow.md).

## 4. Herramientas

Los agentes tienen MCPs y CLI. Usarlos cuando el dato está afuera del repo;
no inventar tickets, PRs ni estado remoto de memoria.

- **Git local** para ramas, commit y push. Ver [git-workflow.md](./git-workflow.md).
- **GitHub** (comando [create-pr](../commands/create-pr.md), MCP) para
  crear o actualizar el PR. No para el día a día de git. Playbooks:
  [openspec/commands/](../commands/README.md).
- **Jira** (MCP) solo si la tarea trae un ticket. No inventar claves de
  proyecto ni subtasks si no hay ticket.
- **No agregar dependencias** sin justificarlo en el `proposal.md` del
  change.

## 5. Estándares por área

| Documento | Cuándo leerlo |
|---|---|
| [Estándares del servicio IA](./ai-service-standards.md) | Cualquier cambio en `ai-service/` |
| [Estándares del BFF](./bff-standards.md) | Route Handlers o `lib/ai-service/` |
| [Estándares de frontend](./frontend-standards.md) | Páginas, componentes, tema, nav |
| [Flujo de git](./git-workflow.md) | Ramas, commits, PRs |
| [Rutas de la consola](./app-routes.md) | Antes de borrar o “limpiar” archivos de `business-backend/app/` |
| [Comandos](../commands/README.md) | Playbooks: plan → develop → docs → commit → PR |
| [project.md](../project.md) | Stack, layout, arquitectura, comandos |
| [openspec/specs/](../specs/) | Comportamiento de producto de la capability que se toca |

## 6. Despliegue

Cada proyecto va a **su** plataforma. Las dos despliegan desde GitHub
por su integración nativa. **CI no despliega** — reproducirlo en YAML
sería reimplementar lo que Railway y Vercel ya hacen, con rollback.

| | Railway | Vercel |
|---|---|---|
| Proyecto | `ai-service/` | `business-backend/` |
| Root directory | `ai-service` | `business-backend` |
| Build | `ai-service/Dockerfile` | Next.js (`pnpm build`) |
| Healthcheck | `GET /health` | — |
| Variables | `DATABASE_URL`, claves de proveedor, `TENANT_ID`, `DOC_VERSION`, `CORPUS_ROOT` | `AI_SERVICE_URL` (URL pública de Railway; **privada**, sin `NEXT_PUBLIC_`) |
| No redesplegar de más | *Watch Paths* = `ai-service/**` | `vercel.json` `ignoreCommand`: no build si el commit no toca este directorio |

Un commit que solo toca `ai-service/` no debe redesplegar Vercel. Uno
que solo toca `business-backend/` no debe redesplegar Railway. El
detalle por stack está en [ai-service-standards.md](./ai-service-standards.md)
y [bff-standards.md](./bff-standards.md).

## 7. Qué puede viajar al repo

El repo es público mientras se evalúa el proyecto.

- **Afuera:** `data/` (documentos fuente y el export de `WINDOWS`), `.env`.
- **Adentro:** `evals/golden_retrieval.json` y `evals/golden_curated.json`,
  aunque lleven códigos de transacción y títulos reales — son la evidencia
  de que las mediciones son reproducibles. Decidido el 2026-09-02; no
  volver a proponer excluirlos.

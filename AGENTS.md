# AGENTS.md — instrucciones para agentes

Punto de entrada canónico para CUALQUIER agente de código o persona que
trabaje en este repo. Agnóstico de modelo y de harness a propósito: sin
nombres de modelos, sin herramientas de un proveedor puntual, sin slash
commands. Los archivos específicos de cada harness (`CLAUDE.md`,
`.cursor/rules/*`, `.github/copilot-instructions.md`, ...) DEBEN quedar
como punteros finos a este archivo, así hay exactamente un lugar que
actualizar.

---

## 1. La fuente de verdad

`openspec/specs/` describe **qué hace el sistema hoy**. Es normativo: si
el código y la spec no coinciden, eso es un bug en uno de los dos — nunca
algo para dejar sin resolver. Leé la spec de la capability antes de cambiar
código en su área, y actualizala en el mismo cambio que cambia el
comportamiento.

`openspec/changes/` registra **trabajo en curso**;
`openspec/changes/archive/` registra **por qué las cosas llegaron a ser como
son** — las decisiones y las alternativas descartadas. El código y los tests
dicen *qué*; el archivo dice *por qué*.

```
openspec/
├── project.md                        # stack, arquitectura, convenciones, comandos
├── AGENTS.md                         # formato y plantillas de specs/changes (autoridad de formato)
├── specs/<capability>/spec.md        # VERDAD ACTUAL — qué hace NUESTRO sistema hoy
├── domain/<tema>.md                  # REFERENCIA — el sistema FUENTE (VisualTIME) y su corpus
└── changes/
    ├── <change-id>/                  # en curso: proposal.md, tasks.md, design.md?, specs/ (deltas)
    └── archive/<YYYY-MM-DD>-<id>/    # completados
```

`specs/` y `domain/` no se mezclan: `specs/` es normativo sobre nuestro código,
`domain/` es referencia sobre el sistema que consumimos. En `domain/`, toda
afirmación lleva su estado de evidencia (`[VALIDADO-BD]`, `[TÁCITO]`,
`[HIPÓTESIS]`, `[VERIFICADO-CORPUS]`) — nunca colapsar una hipótesis en un
hecho. Detalle en `openspec/AGENTS.md`.

## 2. El ciclo de trabajo

Para cualquier cosa más allá de un typo o un fix de una línea:

1. **Proponer** — crear `openspec/changes/<change-id>/` con `proposal.md`
   (por qué + qué cambia), `tasks.md` (el checklist), los deltas de spec en
   `specs/<capability>/spec.md`, y `design.md` cuando el enfoque técnico
   tenga trade-offs reales. `<change-id>` es kebab-case y empieza con verbo
   (`add-embedding-layer`, `fix-table-repair-gap`).
2. **Implementar** — trabajar el checklist de `tasks.md`, tachando ítems a
   medida que entran.
3. **Verificar** — `uv run pytest` y `uv run ruff check .` desde
   `ai-service/`, más lo que pidan las tasks del cambio. Un cambio no está
   listo mientras haya un check en rojo.
4. **Archivar** — integrar los deltas en `openspec/specs/`, y mover la
   carpeta del cambio a `openspec/changes/archive/<YYYY-MM-DD>-<change-id>/`.

Ir directo al código se permite solo para cambios que no alteran ningún
comportamiento documentado (formato, comentarios, un test que fija
comportamiento existente). Si terminás escribiendo la spec después del
código, decilo en el proposal en vez de antedatarlo.

## 3. Reglas no negociables

- **Verificar el formato antes de cerrar**: `python scripts/validate_specs.py`.
  Es un script pelado sin dependencias externas, así que cualquier agente,
  cualquier harness y CI lo corren igual.
- **Nunca borrar información de negocio en silencio.** Son reglas de negocio
  de seguros. Una celda de tabla perdida, una falla de parseo tragada, o un
  documento que produce cero chunks sin avisar es un defecto, no un error de
  redondeo: tiene que advertir, o reportarse, o fallar fuerte.
- **No inventar comportamiento en las specs.** Una spec afirma lo que el
  código realmente hace — verificalo contra el código o un test antes de
  escribirla. Un comportamiento deseado pero no construido va en un
  proposal, nunca en `openspec/specs/`.
- **Código en inglés, comentarios bilingües `EN || ES`.** Ver
  `openspec/project.md` para la convención completa y su única excepción
  (datos de dominio literales en español).
- **No agregar dependencias** sin justificarlo en el `proposal.md` del cambio.
- **Qué puede viajar al repo público.** El repo es público mientras se evalúa
  el proyecto. `data/` queda afuera —los documentos fuente y el export de
  `WINDOWS` son del cliente— y `.env` también. `evals/golden_retrieval.json` y
  `evals/golden_curated.json` **sí** van al repo por decisión del dueño del
  repo, aunque lleven códigos de transacción y títulos reales: son la evidencia
  de que las mediciones son reproducibles y sin ellos los números no se pueden
  auditar. Decidido el 2026-09-02; no volver a proponer excluirlos.

## 4. Comandos

Este repo es un monorepo de dos proyectos: `ai-service/` (el servicio Python) y
`business-backend/` (el frontend y backend de negocio). Los comandos del
servicio corren **desde `ai-service/`**:

```bash
cd ai-service
uv sync                                   # instalar dependencias
uv run pytest                             # tests
uv run ruff check .                       # lint
uv run uvicorn app.main:app --reload      # servidor (Swagger en /docs)
```

Los de la consola web, **desde `business-backend/`**:

```bash
cd business-backend
npm install
npm run dev                               # desarrollo
npm run lint                              # eslint
npm run build                             # build; corre TypeScript
```

El validador de specs corre **desde la raíz** y sin `uv` — es stdlib puro para
que cualquier harness y CI lo corran igual:

```bash
python scripts/validate_specs.py          # validar specs/changes
```

## 5. Agregar otro harness

Creá el archivo que el harness espera y hacelo un puntero, nunca una
copia. Dos copias de estas instrucciones se desincronizan en una semana; una
copia más punteros, no. Si un harness necesita configuración legible por
máquina (un archivo de reglas, una allow-list), limitala a la mecánica de
ese harness y dejá las convenciones acá.

```markdown
Ver [AGENTS.md](AGENTS.md) para saber cómo trabajar en este repo.
```

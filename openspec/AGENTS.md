# Formato de specs y changes || Spec and change format

Authoritative format reference. `scripts/validate_specs.py` enforces exactly
what is written here, so this file and the validator move together.

|| Referencia autoritativa de formato. `scripts/validate_specs.py` valida
exactamente lo que está escrito acá, así que este archivo y el validador se
mueven juntos.

---

## Tres clases de documento, que no se mezclan || Three kinds of document

The commonest way this structure rots is putting the right content in the wrong
place. The test is *whose behavior does this describe?*

| Carpeta | Describe | Normativo sobre |
|---|---|---|
| `openspec/specs/` | **nuestro** servicio, hoy | nuestro código |
| `openspec/domain/` | el sistema **fuente** (VisualTIME) y su corpus | nada — es referencia |
| `openspec/changes/` | trabajo propuesto o en curso | nada hasta archivarse |

Knowledge about VisualTIME — its tables, its menu tree, its naming conventions,
how its documents are shaped — is **reference**, not a requirement on us. It
belongs in `domain/`. Turning it into a `### Requirement:` would assert that
our code already honors it, which is how a source of truth starts lying.

|| El modo más común en que esta estructura se podrida es poner el contenido
correcto en el lugar equivocado. La prueba es *¿de quién describe el
comportamiento?* El conocimiento sobre VisualTIME —sus tablas, su árbol de
menú, sus convenciones de nombres, la forma de sus documentos— es
**referencia**, no un requerimiento sobre nosotros: va en `domain/`.
Convertirlo en un `### Requirement:` afirmaría que nuestro código ya lo
cumple, que es la forma en que una fuente de verdad empieza a mentir.

### `openspec/domain/`

Free-form markdown, one file per subject, kebab-case. No required section
structure — but every claim SHALL carry its evidence status, because the
difference between a validated fact and a hypothesis decides whether the code
may rely on it:

- `[VALIDADO-BD]` — validado contra la base real.
- `[TÁCITO]` — conocimiento tácito de una persona; no verificable automáticamente.
- `[HIPÓTESIS]` — planteado como hipótesis, pendiente de validar.
- `[VERIFICADO-CORPUS]` — verificado contra los archivos reales; indicar cómo.

Never flatten a hypothesis into a fact, and record who supplied the knowledge
and when.

|| Markdown libre, un archivo por tema, kebab-case. Sin estructura de
secciones obligatoria — pero toda afirmación DEBE llevar su estado de
evidencia, porque la diferencia entre un hecho validado y una hipótesis decide
si el código puede apoyarse en él. Nunca colapsar una hipótesis en un hecho, y
registrar quién aportó el conocimiento y cuándo.

## Capabilities

A capability is one coherent, named ability of the system — not a file, not a
class. `document-chunking` is a capability; `functional_spec.py` is not. Names
are kebab-case and live at `openspec/specs/<capability>/spec.md`.

|| Una capability es una habilidad coherente y nombrada del sistema — no un
archivo, no una clase. `document-chunking` es una capability;
`functional_spec.py` no. Los nombres van en kebab-case y viven en
`openspec/specs/<capability>/spec.md`.

## Plantilla de spec (verdad actual) || Spec template (current truth)

```markdown
# <capability> Specification

## Purpose
Una o dos frases: qué cubre esta capability y por qué existe.

## Requirements
### Requirement: <frase normativa corta>
Texto narrativo que describe el comportamiento normativo. Usa SHALL para lo
obligatorio. Este texto es obligatorio: un `### Requirement:` sin cuerpo
antes de sus escenarios es un error de formato.

#### Scenario: <nombre corto>
- **WHEN** <condición o disparador>
- **THEN** <resultado observable>
- **AND** <resultado adicional, opcional>
```

Rules:

- Every `### Requirement:` needs descriptive text BEFORE its first
  `#### Scenario:`.
- Every requirement needs at least one scenario.
- Scenarios use `#### Scenario:` headers with `- **WHEN**` / `- **THEN**`
  bullets — never bare bullets that merely start with the words WHEN/THEN.
- A spec states what the code does **today**. Aspirations go in a proposal.

|| - Todo `### Requirement:` necesita texto descriptivo ANTES de su primer
  `#### Scenario:`.
- Todo requirement necesita al menos un escenario.
- Los escenarios usan headers `#### Scenario:` con bullets `- **WHEN**` /
  `- **THEN**` — nunca bullets pelados que solo empiecen con WHEN/THEN.
- Una spec afirma lo que el código hace **hoy**. Las aspiraciones van en un proposal.

## Plantilla de change || Change template

`openspec/changes/<change-id>/` — kebab-case, verbo primero.

### `proposal.md` (obligatorio)

```markdown
## Why
El problema, en prosa. Qué duele hoy y qué evidencia lo respalda.

## What Changes
- Cambios concretos, en bullets.

## Capabilities
### New Capabilities
- `<capability>`: una línea de qué habilita.
### Modified Capabilities
- `<capability>`: una línea de qué cambia.

## Impact
- `ruta/al/archivo.py` — qué se toca.
```

### `tasks.md` (obligatorio)

```markdown
# Implementation Tasks

## 1. <Grupo>
- [ ] 1.1 Tarea concreta y verificable.
- [ ] 1.2 Otra.
```

### `design.md` (cuando hay trade-offs reales)

Technical approach, the alternatives considered, and why they lost. Skip it
for a mechanical change; write it when a future reader would otherwise ask
"why on earth was it done this way?".

|| Enfoque técnico, las alternativas consideradas, y por qué perdieron.
Omitilo en un cambio mecánico; escribilo cuando un lector futuro, si no,
preguntaría "¿por qué demonios se hizo así?".

### `specs/<capability>/spec.md` (deltas)

A delta file declares only what moves, under operation headers. It MUST start
with the title + an operation header — no prose before them.

|| Un archivo de delta declara solo lo que se mueve, bajo headers de
operación. DEBE empezar con el título + un header de operación — sin prosa
antes de ellos.

```markdown
# <capability> Delta Specification

## ADDED Requirements
### Requirement: ...
...

## MODIFIED Requirements
### Requirement: ...
...

## REMOVED Requirements
### Requirement: ...
Razón del retiro.
```

Valid operations: `ADDED`, `MODIFIED`, `REMOVED`, `RENAMED`.

## Archivado || Archiving

On completion: fold the deltas into `openspec/specs/`, then move the folder to
`openspec/changes/archive/<YYYY-MM-DD>-<change-id>/`. The date is the
completion date. The archived folder keeps its own deltas as the historical
record of that change.

|| Al completar: integrar los deltas en `openspec/specs/`, y mover la carpeta
a `openspec/changes/archive/<YYYY-MM-DD>-<change-id>/`. La fecha es la de
completado. La carpeta archivada conserva sus propios deltas como registro
histórico de ese cambio.

## Checklist previo a cerrar || Pre-close checklist

- [ ] `uv run python scripts/validate_specs.py` pasa.
- [ ] `uv run pytest` y `uv run ruff check .` pasan.
- [ ] Las specs afectadas describen el comportamiento real, verificado contra
      código o test — no el intencionado.
- [ ] `tasks.md` no tiene ítems sin tachar que en realidad ya estén hechos.

## Why

El programa del Master fija el layout del repo: un monorepo de dos proyectos,
`ai-service/` para el servicio FastAPI y `business-backend/` para el frontend y
el backend de negocio. El `CLAUDE.md` de la rama `session_16` lo declara como la
estructura del programa, y aclara que la implementación Ruby de
`business-backend/` es solo la de referencia — **cada estudiante puede usar otra
stack**, pero el lugar es ese.

Este repo tiene el servicio en la raíz (`app/`, `scripts/`, `tests/`,
`alembic/`, `pyproject.toml`). Eso deja al proyecto sin lugar donde poner la
segunda app sin inventar una convención propia, y diverge del layout contra el
que se evalúa.

Este cambio es **puramente estructural**: mueve archivos y actualiza rutas en la
documentación. Ningún comportamiento cambia. Va primero y solo, separado de
[`add-web-console`](../add-web-console/proposal.md), por dos razones: se
verifica solo (`pytest` en verde desde `ai-service/` es la prueba entera), y un
lector futuro que pregunte "¿por qué el servicio está bajo `ai-service/`?" tiene
que encontrar un change que se llame exactamente así.

## What Changes

**Se mueve a `ai-service/`** (con `git mv`, para que el historial siga cada
archivo):

`app/` · `tests/` · `alembic/` · `alembic.ini` · `pyproject.toml` · `uv.lock` ·
`evals/` · `.env.example` · `README.md` · y todo `scripts/` **menos**
`validate_specs.py`.

Fuera del control de versiones, a mano: `data/` (76 MB, documentos del cliente,
gitignoreado), `.env` y `.venv/`.

**Se queda en la raíz**, y cada caso tiene su razón (detalle en `design.md`):

| queda en la raíz | por qué |
|---|---|
| `openspec/`, `AGENTS.md`, `CLAUDE.md` | documentan el repo, no una de sus apps |
| `scripts/validate_specs.py` | deriva la raíz del repo de su propia ubicación, y valida `openspec/` |
| `docker-compose.yml` | el nombre del proyecto de compose sale del directorio: moverlo renombra el volumen y vacía la base |
| `.gitignore`, `.github/` | son del repo |
| `README.md` (nuevo, fino) | portada del monorepo; el actual pasa a ser el del servicio |

**Deliberadamente NO se renombra** —la misma regla que el curso fijó en su
sesión 15 al renombrar sus directorios, y por la misma razón: el nombre de la
carpeta cambió, el vocabulario interno no.

- La raíz del paquete Python sigue siendo `app.*`. Ni un import cambia.
- `TENANT_ID` y `DOC_VERSION` conservan sus valores: están estampados en las
  57.101 filas de `chunks` y forman parte de su clave única. Cambiarlos
  huerfaniza el corpus cargado.
- La base sigue siendo `visualtime_rag`, el volumen sigue siendo `pgdata` y el
  contenedor `visual-time-rag-postgres`.

**Los comandos ganan un `cd ai-service`**, con una excepción: el validador de
specs corre desde la raíz y sin `uv` (es stdlib puro, que es justamente la
propiedad que lo deja sobrevivir a la mudanza).

## Capabilities

### New Capabilities
(ninguna)

### Modified Capabilities
(ninguna — ningún requirement cambia. Este change es **deliberadamente
delta-free**: mover un archivo no altera lo que el código hace, y las specs
siguen describiendo el mismo comportamiento. Lo que cambia son rutas en prosa,
y `design.md` explica por qué tampoco se reescriben.)

## Impact

- ~40 referencias a rutas y comandos que sí se actualizan: `AGENTS.md` (6),
  `openspec/project.md` (13), `README.md` (19).
- 25 menciones de rutas `app/...` y `scripts/...` en 10 specs y 1 doc de
  `domain/` que **no** se tocan — pasan a leerse relativas a `ai-service/`, por
  una regla declarada una sola vez en `project.md`.
- **Cero ediciones de código.** Verificado: cada script y cada test deriva su
  raíz de `Path(__file__)` (`sys.path.insert(0, ...parent.parent)` en los 8
  scripts y `alembic/env.py`; `parents[3]` en los tests de `tests/generation/rag/`),
  así que siguen apuntando a lo correcto siempre que `data/` viaje con el
  código. `alembic.ini` usa `%(here)s/alembic`.
- Sin dependencias nuevas. Sin migraciones.

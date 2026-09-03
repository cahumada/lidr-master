# Implementation Tasks

## 1. Preparación
- [ ] 1.1 Commitear o stashear lo que haya en curso: hoy `app/ingestion/pipeline.py`
      y `tests/ingestion/test_pipeline.py` están modificados sin commitear, y un
      `git mv` masivo sobre un árbol sucio es imposible de leer en el diff.
- [ ] 1.2 Correr `uv run pytest` **antes** de mover y anotar el resultado. Es la
      línea de base contra la que se compara después; sin ella, una falla
      posterior no se puede atribuir.

## 2. La mudanza (versionado)
- [ ] 2.1 `git mv` a `ai-service/`: `app/`, `tests/`, `alembic/`, `alembic.ini`,
      `pyproject.toml`, `uv.lock`, `evals/`, `.env.example`, `README.md`.
- [ ] 2.2 `git mv scripts/*.py ai-service/scripts/` **excepto**
      `validate_specs.py`, que se queda en `scripts/` (ver `design.md` §3).
- [ ] 2.3 Verificar que `docker-compose.yml`, `openspec/`, `AGENTS.md`,
      `CLAUDE.md`, `.gitignore` y `.github/` siguen en la raíz.
- [ ] 2.4 Confirmar que ningún archivo Python cambió de contenido:
      `git diff --stat` sobre el commit de la mudanza debe mostrar solo
      renombrados (`R`), cero modificaciones.

## 3. La mudanza (fuera de git)
- [ ] 3.1 Mover `data/` a `ai-service/data/` a mano. Es el paso que ningún
      comando de git hace y del que dependen 5 tests.
- [ ] 3.2 Mover `.env` a `ai-service/.env`.
- [ ] 3.3 Borrar `.venv/` de la raíz y regenerar con `uv sync` desde
      `ai-service/` (un venv no se muda: lleva rutas absolutas adentro).
- [ ] 3.4 Verificar que los patrones de `.gitignore` siguen cubriendo todo: no
      llevan `/` inicial, así que `data/`, `.env` y `.venv/` matchean a
      cualquier profundidad. Confirmar con `git status --ignored` que
      `ai-service/data/` sigue ignorado.

## 4. Documentación
- [ ] 4.1 `README.md` nuevo y fino en la raíz: qué es el monorepo, sus dos
      apps, y links a los README de cada una. El README actual (12 KB, todo del
      servicio) ya está en `ai-service/README.md` por 2.1 — actualizarle los
      comandos, no reescribirlo.
- [ ] 4.2 `AGENTS.md` §4: los comandos del servicio llevan `cd ai-service`; el
      validador queda como `python scripts/validate_specs.py` desde la raíz.
- [ ] 4.3 `openspec/project.md`: el layout del monorepo, con la regla de que
      **las rutas de código en las specs del servicio IA son relativas a
      `ai-service/`**, y la lista de lo que NO se renombró (`app.*`,
      `TENANT_ID`/`DOC_VERSION`, `visualtime_rag`, `pgdata`).
- [ ] 4.4 No tocar las 25 menciones de rutas en `openspec/specs/` ni en
      `openspec/domain/` (ver `design.md`).

## 5. Verificación
- [ ] 5.1 Desde `ai-service/`: `uv sync`, `uv run pytest` con el mismo
      resultado que 1.2, `uv run ruff check .`.
- [ ] 5.2 Desde `ai-service/`: `uv run uvicorn app.main:app --reload` levanta y
      `/health` responde.
- [ ] 5.3 Desde la raíz: `docker compose up -d` y confirmar que la base tiene
      las filas de siempre (`select count(*) from chunks`) — la prueba de que
      el volumen no se renombró.
- [ ] 5.4 Desde la raíz: `python scripts/validate_specs.py` en verde.
- [ ] 5.5 Un script del pipeline en modo seco desde `ai-service/`
      (`uv run python scripts/chunk_corpus.py --help` como mínimo, o un
      `--dry-run` si hay corpus a mano) — confirma el `sys.path` derivado.
- [ ] 5.6 Archivar el change.

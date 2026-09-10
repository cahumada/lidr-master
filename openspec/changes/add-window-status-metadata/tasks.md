# Implementation Tasks

## 1. El estado en el árbol de navegación
- [x] 1.1 En `app/generation/rag/navigation.py`, agregar el catálogo
  `WINDOW_STATUSES = {"1": "Activo", "2": "En proceso de instalación",
  "3": "Acceso restringido"}` con la referencia a `TABLE26` en el comentario, y
  `ACTIVE_WINDOW_STATUS = "1"`.
- [x] 1.2 `NavigationTree` guarda el estado por código y expone
  `window_status(code) -> str | None` (nombre declarado). El `4` se resuelve como
  `3` **contando** las ocurrencias; un valor fuera del catálogo devuelve `None`.
- [x] 1.3 El constructor tolera filas sin la columna de estado, igual que hoy
  tolera las de tres columnas: `if len(row) > 5 and row[5]`. Sin el dato, el
  estado queda no resuelto y nada más cambia.
- [x] 1.4 `NavigationLocation` gana `window_status: str | None` con su
  descripción bilingüe, y `locate()` lo completa.
- [x] 1.5 El log `navigation_tree_loaded` suma el conteo por estado y el conteo
  de `4` normalizados — si la corrida trae más errores de datos, tiene que verse.

## 2. Armar el árbol desde el mirror
- [x] 2.1 `BUSINESS_DB_ENV` y `BUSINESS_DB_RUN_ID` en `app/config.py`, con el
  comentario de por qué la corrida se nombra y no se descubre.
- [x] 2.2 `load_navigation_tree_from_mirror(...)` en `navigation.py`: lee de
  `visualtime.business_data` (`table_name='WINDOWS'`, filtrando por tenant, env y
  `run_id`) y devuelve un `NavigationTree`. Consulta de solo lectura, sin ORM
  propio del mirror — nada de modelos declarativos sobre `visualtime` (Alembic no
  debe verlo).
- [x] 2.3 Falla fuerte si el `run_id` configurado no existe o no tiene filas de
  `WINDOWS`: un árbol vacío que se lee como "ningún código resuelve" es peor que
  un error al arrancar.
- [x] 2.4 `app/dependencies.py` elige la fuente: `BUSINESS_DB_RUN_ID` puesto →
  mirror; vacío → `WINDOWS_TREE_PATH`. El chunker sigue recibiendo un
  `NavigationTree` y no conoce la base.

## 3. Contrato y persistencia
- [x] 3.1 `ChunkMetadata.window_status` en `app/generation/rag/schemas.py`, con
  `Field(description=...)` bilingüe para que aparezca en la pestaña Schema.
- [x] 3.2 `SearchHit.window_status` y su mapeo en `search_hits_from_chunks`.
- [x] 3.3 Columna `window_status: Mapped[str | None] = mapped_column(String(48))`
  en `app/generation/rag/store/models.py`, junto a `window_type_name`. Sin índice:
  no hay filtro en este change.
- [x] 3.4 Migración Alembic con la columna nullable.
- [x] 3.5 `app/generation/rag/store/repository.py`: la columna se selecciona y
  viaja al hit; el `INSERT ... ON CONFLICT` la actualiza como el resto de la
  metadata.

## 4. Estampado y prompt
- [x] 4.1 En `functional_spec.py`, junto a
  `chunk.metadata.window_type_name = location.window_type_name`, estampar
  `window_status`.
- [x] 4.2 En `app/generation/rag/context_budget.py`, `render_hit_block` agrega una
  línea de advertencia **solo si** `window_status` está resuelto y no es `Activo`
  — con el estado declarado textual, nunca la palabra "baja".
- [x] 4.3 Verificar que `fit_to_budget` cuenta esa línea: es el mismo renderer,
  así que alcanza con un test que compare el conteo con y sin advertencia.

## 5. Backfill
- [x] 5.1 `ai-service/scripts/backfill_window_status.py`: `UPDATE public.chunks`
  cruzando `document_id` contra `WINDOWS` de la corrida configurada. Toma
  `--tenant`, `--doc-version`, `--run-id` y `--dry-run`.
- [x] 5.2 No toca `content_hash`, `embedding` ni `token_count`. Un test o una
  aserción en el script lo garantiza.
- [x] 5.3 Reporta filas actualizadas por estado, cuántos documentos del corpus no
  matchearon ninguna ventana, y cuántos `4` se normalizaron. Idempotente:
  correrlo dos veces da el mismo resultado.

## 6. Tests
- [x] 6.1 `tests/generation/rag/test_navigation.py`: estado resuelto, `4`→`3` con
  su conteo, valor desconocido → `None`, fila sin columna de estado → `None`.
- [x] 6.2 `tests/generation/rag/test_functional_spec.py`: un chunk de una
  transacción con estado lo lleva estampado; sin árbol, ausente.
- [x] 6.3 `tests/generation/rag/test_context_budget.py`: con estado `Activo` o no
  resuelto, `render_hit_block` devuelve **exactamente** lo mismo que antes del
  change; con `Acceso restringido`, agrega la advertencia.
- [x] 6.4 `tests/store/test_store_integration.py`: la columna persiste y vuelve
  en el hit.
- [x] 6.5 Loader desde el mirror con un doble: filas → árbol, y `run_id` sin
  filas → error.
- [x] 6.6 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.

## 7. Medición
- [x] 7.1 Correr el backfill en la base real y anotar los conteos en el proposal:
  cuántos chunks quedaron con cada estado (se esperan ~574 documentos con estado
  distinto de `Activo`).
- [x] 7.2 Re-correr el eval de fidelidad y anotar antes/después. Las preguntas
  que no toquen transacciones no contempladas tienen que dar **idéntico**; si
  alguna cambia, hay que explicar por qué.
- [x] 7.3 Agregar al golden set al menos una pregunta sobre una transacción con
  `Acceso restringido` — es el caso de regresión de este change.

## 8. Specs y docs
- [x] 8.1 Deltas en `openspec/changes/add-window-status-metadata/specs/`
  (`chunk-schema`, `document-chunking`, `retrieval`).
- [x] 8.2 `python scripts/validate_specs.py` sin errores desde la raíz.
- [x] 8.3 Sin cambios de estándar: `ai-service-standards.md` y `app-routes.md`
  no se tocan (no hay ruta nueva ni convención nueva).
- [x] 8.4 Anotar en `openspec/domain/visualtime-database-metadata.md` §13 los
  huecos que este change cierra y los que deja abiertos.

# Implementation Tasks

## 1. Estado de la selección
- [ ] 1.1 `app/domain/business_db_store.py` (nuevo): `BusinessDbSelectionRow`
  (`tenant_id`, `env`, `run_id`, `status`, `activated_at`, `activated_by`) con
  `UniqueConstraint(tenant_id, env, run_id)` y un índice parcial único sobre
  `status = 'active'` por `tenant_id` — la regla la garantiza la base, no el código.
- [ ] 1.2 `BusinessDbStampRow` (`tenant_id`, `doc_version`, `run_id`,
  `stamped_at`, `rows_updated`), una fila por `(tenant_id, doc_version)`.
- [ ] 1.3 Migración Alembic con las dos tablas y el índice parcial.
- [ ] 1.4 `resolve_active_run(session, settings, tenant_id)`: la fila activa
  gana; si no hay ninguna, cae a `BUSINESS_DB_RUN_ID` con origen `default`; si
  tampoco hay, `None` con su razón — nunca "la más reciente". El default **no**
  se materializa como fila.

## 2. Endpoints
- [ ] 2.1 `app/api/business_db.py` (nuevo). `GET /business-db/runs`: lista de
  `visualtime.extraction_runs` con `run_id`, `created_at_utc`,
  `extractor_version`, `loaded_metadata`, `loaded_dependencies`, `loaded_data`,
  `manifest_sha256`, y cuál es la vigente con su origen (`selected` / `default`).
  Solo lectura sobre el mirror.
- [ ] 2.2 `POST /business-db/runs/{run_id}/activate`, con `activated_by` opcional
  en el body. Router delgado: transporte, `HTTPException`, `response_model`.
- [ ] 2.3 Rechazos, cada uno con su código: `404` si el `run_id` no existe para
  ese tenant; `409` si `loaded_data = false`. Ninguno acepta y descarta en
  silencio. Un valor en `BUSINESS_DB_RUN_ID` **no** es motivo de rechazo: es el
  default, no un candado.
- [ ] 2.4 Registrar el router en `app/main.py` y anotar la ruta en
  `openspec/standards/app-routes.md`.

## 3. Consumir la corrida activa
- [ ] 3.1 `get_navigation_tree` cacheado por `(tenant, env, run_id)` en
  `app/generation/rag/navigation.py`. Activar otra corrida elige otra clave.
- [ ] 3.2 `app/dependencies.py`: `get_functional_spec_chunker()` deja de ser un
  `@lru_cache` sin argumentos —hoy quedaría pegado a la corrida que se resolvió
  al arrancar el proceso— y pasa a estar keyed por corrida.
- [ ] 3.3 `render_hit_block` en `app/generation/rag/context_budget.py` recibe el
  estado resuelto del **árbol activo** en lugar de leer `hit.window_status`. La
  regla de renderizar solo cuando no es `Activo` no cambia.
- [ ] 3.4 La corrida vigente y su origen (`selected` / `default`) en
  `ServiceConfigResponse` (`app/api/config.py`), para que la consola la muestre
  con el resto.

## 4. El sello del corpus
- [ ] 4.1 `scripts/backfill_window_status.py` escribe `business_db_stamp` al
  terminar: con qué corrida se estampó, cuándo y cuántas filas.
- [ ] 4.2 Exponer el sello junto a la corrida activa, para que la consola pueda
  mostrar *"estampado con X · activa Y"* y ofrecer re-estampar.

## 5. Tests
- [ ] 5.1 `tests/domain/test_business_db_store.py`: la fila activa le gana al
  valor de configuración; sin fila, gana la configuración con origen `default`;
  sin ninguno de los dos, `None` con razón; resolver por default no escribe
  ninguna fila; dos activas para el mismo tenant son imposibles (la base lo
  rechaza).
- [ ] 5.2 `tests/api/test_business_db.py`: el listado marca la vigente y su
  origen; activar una corrida sin `loaded_data` da `409`; un `run_id`
  inexistente da `404`; con `BUSINESS_DB_RUN_ID` puesto, activar otra corrida
  **funciona** y pasa a origen `selected`.
- [ ] 5.3 `tests/generation/rag/test_context_budget.py`: el bloque advierte según
  el árbol activo, y cambiar de árbol cambia la advertencia sin tocar la columna
  del chunk.
- [ ] 5.4 Un test que fije que el chunker no queda pegado a una corrida: dos
  resoluciones distintas devuelven chunkers con árboles distintos.
- [ ] 5.5 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.

## 6. Specs
- [ ] 6.1 Delta `specs/extraction-run-selection/spec.md` (capability nueva).
- [ ] 6.2 Delta `specs/retrieval/spec.md` con el `MODIFIED` que supersede el
  requirement de `add-window-status-metadata`.
- [ ] 6.3 `python scripts/validate_specs.py` sin errores desde la raíz.
- [ ] 6.4 Sin cambios en `ai-service-standards.md`; sí una fila en
  `app-routes.md` (ver 2.4).

## 7. Dependencias y secuencia
- [ ] 7.1 Este change asume `add-window-status-metadata` aterrizado: sale de main
  después de ese PR, no antes.
- [ ] 7.2 `BUSINESS_DB_RUN_ID` se queda como está en el despliegue: pasa a ser el
  default y no bloquea nada. Actualizar su comentario en `app/config.py` y en
  `.env.example` para que diga **valor por defecto**, no pin — el comentario
  actual quedaría afirmando lo contrario de lo que hace el código.
- [ ] 7.3 La pantalla de administración es un change de `web` con
  `/plan-web`, y depende de `add-console-authentication` para el gate de rol.
  **No** se implementa acá.

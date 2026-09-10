## Why

El servicio lee el mirror de la base de VisualTIME de **una** corrida del
extractor, y hoy cuál es lo decide una variable de entorno
(`BUSINESS_DB_RUN_ID`, introducida por `add-window-status-metadata`). Cambiar de
corrida exige un redeploy.

Eso no alcanza para operar. Hay ya tres corridas cargadas en `extraction_runs`
—dos de `PROD` y una de `DEV`, con distinto `created_at_utc` y distinto grado de
carga— y quien opera el servicio necesita poder mirar qué corridas existen,
elegir una y trabajar con ella. Es el mismo problema que
[providers_store.py](../../../ai-service/app/domain/providers_store.py) ya
resolvió para los proveedores: *"es tabla y no env var porque los ids de modelo
cambian seguido y agregar uno no debería necesitar un redeploy"*.

Y hay un problema de consistencia que hoy queda abierto: `window_status` está
estampado en 56.537 chunks desde la corrida `20260909_214921`. Si mañana se
activa otra corrida, esa columna queda vieja y nada lo dice.

## What Changes

- **Nueva tabla `business_db_selection`** en el esquema del servicio: qué corrida
  del mirror está activa, una sola por tenant, garantizado por índice parcial —
  la misma forma con la que `corpus_versions` garantiza una versión activa.
  **No se escribe nada en `visualtime.*`**: el mirror es de otro repo y se lee.
- **`GET /business-db/runs`** lista las corridas de `extraction_runs` con lo que
  hace falta para elegir: `run_id`, `created_at_utc`, `extractor_version`, los
  tres flags de carga, `manifest_sha256` y cuál está activa.
- **`POST /business-db/runs/{run_id}/activate`** cambia la selección. **Rechaza
  una corrida con `loaded_data = false`**: el árbol de navegación vive en
  `business_data`, y activar una corrida sin datos dejaría todos los códigos sin
  resolver. Misma regla que *"una versión a medias no debe poder activarse sola"*.
- **`BUSINESS_DB_RUN_ID` pasa a ser el valor por defecto**, no un override: es la
  corrida con la que arranca una instalación donde nadie eligió todavía. En
  cuanto hay selección, la selección gana — quien opera el producto está por
  encima de quien lo despliega para esta decisión. Es el mecanismo de **semilla**
  que `providers_store` usa para el catálogo de modelos, no el de override que
  reserva para las credenciales. La corrida vigente informa su origen
  (`selected` / `default`), y la semilla nunca se materializa como fila: una fila
  haría parecer que alguien eligió, y nadie eligió.
- **El camino de respuesta resuelve el estado del árbol activo**, no de la columna
  `window_status`. Cambiar de corrida se refleja de inmediato y por completo en
  las respuestas, sin job y sin re-embedding. La columna queda como lo que es: un
  valor estampado, con su procedencia.
- **`business_db_stamp`** registra con qué corrida se estampó el corpus
  (`tenant_id`, `doc_version`, `run_id`, `stamped_at`, `rows_updated`), escrito
  por `scripts/backfill_window_status.py`. Es lo que permite mostrar *"corpus
  estampado con X · corrida activa Y"* en lugar de un desfasaje invisible.
- **La corrida activa se expone en `GET /config`**, para que la consola la muestre
  donde ya muestra el resto de la configuración.
- Se registra **quién activó**, como valor **declarado por quien llama**: el
  servicio no tiene identidad propia (la autenticación vive en la consola), así
  que `activated_by` es lo que el BFF informa y así queda etiquetado.

Fuera de alcance:

- **La pantalla de administración y su gate de rol.** El servicio no tiene auth;
  `add-console-authentication` pone los roles `usuario` / `administrador` en el
  token de sesión y gatea las rutas desde la consola. La pantalla es un change de
  `web` y depende de que ese aterrice.
- **Reactivar el backfill automáticamente al cambiar de corrida.** Sería un
  `UPDATE` de 56.537 filas dentro de un request; ver `design.md` §3.

## Capabilities

### New Capabilities

- `extraction-run-selection`: qué corrida del mirror usa el servicio, quién la
  elige, qué se rechaza, y cómo se sabe con qué corrida se estampó el corpus.

### Modified Capabilities

- `retrieval`: la advertencia de estado en el bloque de evidencia se resuelve del
  árbol **activo** y no de la columna estampada. **Supersede** el requirement que
  introduce `add-window-status-metadata`, que este change asume aterrizado.

## Impact

- `ai-service/app/domain/business_db_store.py` — nuevo: las dos tablas, la
  resolución de la corrida vigente y la caída al valor por defecto.
- `ai-service/app/api/business_db.py` — nuevo: los dos endpoints.
- `ai-service/app/main.py` — registrar el router.
- `ai-service/alembic/versions/` — migración de `business_db_selection` y
  `business_db_stamp`.
- `ai-service/app/generation/rag/navigation.py` — caché del árbol por
  `(tenant, env, run_id)`.
- `ai-service/app/dependencies.py` — el chunker deja de ser un singleton sin
  argumentos: hoy tiene el árbol adentro y quedaría pegado a una corrida.
- `ai-service/app/generation/rag/context_budget.py` — `render_hit_block` recibe
  el estado resuelto del árbol activo.
- `ai-service/app/api/config.py` — la corrida activa en `ServiceConfigResponse`.
- `ai-service/scripts/backfill_window_status.py` — escribe `business_db_stamp`.
- `ai-service/tests/domain/`, `tests/api/`, `tests/generation/rag/` — tests.

# Implementation Tasks

## 1. Estado de la selección
- [x] 1.1 `app/domain/business_db_store.py` (nuevo): `BusinessDbSelectionRow`
  (`tenant_id`, `env`, `run_id`, `status`, `activated_at`, `activated_by`) con
  `UniqueConstraint(tenant_id, env, run_id)` y un índice parcial único sobre
  `status = 'active'` por `tenant_id` — la regla la garantiza la base, no el código.
  El índice **no** va por `env`, y es una decisión: el servicio lee de una
  corrida y punto, y una activa por ambiente significaría dos respuestas según
  el env que se preguntara. `env` sí está en la unique de tres columnas, porque
  el mirror identifica una corrida por `(tenant, env, run_id)` — el mismo
  `run_id` en DEV y en PROD son dos corridas.
  Las filas se **acumulan**: una corrida retirada queda con
  `status = 'retired'` en vez de borrarse. Qué corridas estuvieron activas y
  quién activó cada una es el único historial de una decisión que cambia lo que
  dice cada respuesta.
- [x] 1.2 `BusinessDbStampRow` (`tenant_id`, `doc_version`, `run_id`,
  `stamped_at`, `rows_updated`), una fila por `(tenant_id, doc_version)`.
  Lleva también `env`, porque un `run_id` sin su ambiente no identifica una
  corrida y el sello tiene que poder compararse con la activa.
- [x] 1.3 Migración Alembic con las dos tablas y el índice parcial.
  `a4c19d7e2b58`, aplicada. **Y el invariante verificado contra la base, no
  declarado**: dos inserts con `status = 'active'` para el mismo tenant dan
  `UniqueViolation` en
  `uq_business_db_selection_one_active_per_tenant`, y una activa más dos
  retiradas conviven sin problema — el índice es parcial. El modelo se agregó a
  los imports de `alembic/env.py`, o el próximo `--autogenerate` propondría
  borrar las dos tablas (el mismo problema que ya tiene anotado
  `_FOREIGN_TABLES` para las del checkpointer).
- [x] 1.4 `resolve_active_run(session, settings, tenant_id)`: la fila activa
  gana; si no hay ninguna, cae a `BUSINESS_DB_RUN_ID` con origen `default`; si
  tampoco hay, `None` con su razón — nunca "la más reciente". El default **no**
  se materializa como fila.
  Devuelve un `ActiveRun` con `run_id | None` + `origin` + `reason` en vez de un
  `None` pelado: «no hay corrida» y «no hay corrida porque tampoco hay
  configuración» mandan a quien opera a lugares distintos.
  **Y hay una segunda forma de traerla, con una sola regla.** El rebuild corre
  en un thread (`ingestion/runner.py`) y los scripts son un `main()`, así que
  ninguno tiene la sesión async del request: `resolve_active_run_sync` lee la
  fila con psycopg. Los dos llamadores deciden en `_decide`, que es la única
  función que conoce la precedencia — que la regla existiera dos veces es cómo
  el camino async y el batch empiezan a no coincidir sobre qué corrida está
  viva, que es exactamente el defecto del que trata este change.

## 2. Endpoints
- [x] 2.1 `app/api/business_db.py` (nuevo). `GET /business-db/runs`: lista de
  `visualtime.extraction_runs` con `run_id`, `created_at_utc`,
  `extractor_version`, `loaded_metadata`, `loaded_dependencies`, `loaded_data`,
  `manifest_sha256`, y cuál es la vigente con su origen (`selected` / `default`).
  Solo lectura sobre el mirror.
  Suma dos campos que no estaban en el plan y que la consola necesita para no
  ofrecer algo que iba a fallar: `is_active` y `can_activate` (false cuando
  `loaded_data` es false). Y el **sello del corpus viaja con la lista**, para
  que se pueda decir «estampado con X · activa Y» sin una segunda llamada: ese
  desfasaje es lo que esta capability existe para hacer visible.
- [x] 2.2 `POST /business-db/runs/{run_id}/activate`, con `activated_by` opcional
  en el body. Router delgado: transporte, `HTTPException`, `response_model`.
  Un `activated_by` en blanco queda **ausente** y no como string vacío: no se
  inventa un autor, y un `""` guardado se leería como un registro.
- [x] 2.3 Rechazos, cada uno con su código: `404` si el `run_id` no existe para
  ese tenant; `409` si `loaded_data = false`. Ninguno acepta y descarta en
  silencio. Un valor en `BUSINESS_DB_RUN_ID` **no** es motivo de rechazo: es el
  default, no un candado.
  **Verificado contra el mirror real**, que tiene las tres corridas del
  despliegue y solo una con datos: `20260909_174017` (`loaded_data = false`) da
  `409` nombrando la bandera, un `run_id` inventado da `404`, y
  `20260909_214921` activa y cambia el origen de `default` a `selected`. La fila
  del smoke test se borró después.
- [x] 2.4 Registrar el router en `app/main.py` y anotar la ruta en
  `openspec/standards/app-routes.md`. El router entra en la misma tupla que los
  demás, así que hereda el guard del token de `add-service-authentication` sin
  que nadie tenga que acordarse. En `app-routes.md` van las dos filas del
  upstream **y** una nota de que todavía no hay Route Handler del BFF: los
  endpoints existen, la pantalla es un change de `web` (ver 7.3).

## 3. Consumir la corrida activa
- [x] 3.1 `get_navigation_tree` cacheado por `(tenant, env, run_id)` en
  `app/generation/rag/navigation.py`. Activar otra corrida elige otra clave.
  Es `get_navigation_tree_for_run`, con `maxsize=4`: no hay nada que invalidar y
  no hay ventana en la que un worker sirva el árbol viejo y otro el nuevo, y las
  dos versiones pueden convivir mientras terminan los requests en vuelo. El
  loader del CSV sigue siendo `get_navigation_tree`, sin cambios.
- [x] 3.2 `app/dependencies.py`: `get_functional_spec_chunker()` deja de ser un
  `@lru_cache` sin argumentos —hoy quedaría pegado a la corrida que se resolvió
  al arrancar el proceso— y pasa a estar keyed por corrida.
  Quedó partido en tres, porque resolver la corrida es una consulta y el
  chunker lo piden dos mundos:
  - `build_functional_spec_chunker(env, run_id)` — el `@lru_cache`, ahora con la
    corrida en la clave.
  - `get_functional_spec_chunker(session)` — la dependencia de FastAPI, **async**:
    resuelve la activa y delega. Un request servido después de una activación
    recibe el árbol nuevo sin redeploy ni reinicio.
  - `get_functional_spec_chunker_sync()` — para el rebuild y los scripts, que
    corren en un thread y no pueden await.
  Y `resolve_navigation_tree` pasó a **recibir la corrida por argumentos** en vez
  de leerla de settings, que es el punto: una función que la resolviera del
  ambiente pegaría a cada llamador a lo configurado al arrancar.
  **De paso apareció un defecto que no estaba en el plan.** La rama de
  `pipeline.py` para un tenant o una versión distintos de los del despliegue
  leía el **CSV**, que no trae `SSTATREGT`: troceaba todo ese corpus con los
  breadcrumbs sin resolver y `window_status` vacío, en silencio. Ahora usa el
  árbol de la corrida activa como la otra rama.
- [x] 3.3 `render_hit_block` en `app/generation/rag/context_budget.py` recibe el
  estado resuelto del **árbol activo** en lugar de leer `hit.window_status`. La
  regla de renderizar solo cuando no es `Activo` no cambia.
  El resolver (`StatusResolver`) se enhebra por **toda** la cadena
  —`build_budgeted_messages` → `fit_to_budget` → `build_messages` →
  `build_context` → `render_hit_block`— y no solo hasta el renderer: uno que
  llegara al renderer y no al contador haría que el presupuesto cuente de menos
  exactamente las líneas de advertencia que después se emiten. Hay un test que
  lo fija.
  La columna queda como **fallback declarado**, y no es una concesión: si no hay
  árbol tampoco hay corrida activa, así que no hay nada respecto de lo cual la
  columna esté vieja, y su procedencia está en `business_db_stamp`. Lo que no
  puede pasar es que decida la columna habiendo árbol. Se agregó el escenario al
  delta de `retrieval`, que no lo declaraba.
  **Cómo llega la corrida al sintetizador**: como DOS STRINGS en el estado del
  grafo (`active_run_id`, `active_run_env`), resueltas por el router —que es el
  que tiene sesión— y congeladas ahí. No el árbol: el estado se serializa al
  checkpointer y unos MB no van ahí. Efecto secundario deseable: una corrida
  pausada en el gate y retomada después de una activación sigue respondiendo con
  la corrida en la que empezó, porque un turno no debería cambiar de idea sobre
  el mundo a mitad de camino.
- [x] 3.4 La corrida vigente y su origen (`selected` / `default`) en
  `ServiceConfigResponse` (`app/api/config.py`), para que la consola la muestre
  con el resto. `business_db` lleva además el sello y `stamp_matches_active`.
  Verificado: `GET /config` responde
  `{"run_id": "20260909_214921", "env": "PROD", "origin": "default", ...}`.

## 4. El sello del corpus
- [x] 4.1 `scripts/backfill_window_status.py` escribe `business_db_stamp` al
  terminar: con qué corrida se estampó, cuándo y cuántas filas.
  Dos cosas más, y las dos importan:
  - El sello va en la **misma transacción** que el `UPDATE`. Un commit en el
    medio podría dejar la columna estampada sin registro de qué corrida lo hizo,
    que es peor que no estampar: un valor sin procedencia no se puede comprobar
    y el desfasaje vuelve a ser invisible.
  - El default del script pasó a ser la corrida **activa** y no
    `BUSINESS_DB_RUN_ID`. Estampar desde la configurada mientras el servicio
    responde desde la seleccionada crearía justo el desfasaje que esta
    contabilidad existe para mostrar. Los flags siguen ganando, porque
    re-estampar una corrida concreta es una necesidad real.
  `--dry-run` verificado: 2.176 documentos, 666 sin estado, 56.537 filas, y dice
  explícitamente que no escribió el sello.
- [x] 4.2 Exponer el sello junto a la corrida activa, para que la consola pueda
  mostrar *"estampado con X · activa Y"* y ofrecer re-estampar. En los dos
  lugares donde la consola ya mira: `GET /business-db/runs` (campo `stamp`) y
  `GET /config` (`business_db.stamped_run_id` + `stamp_matches_active`).
  `stamp_matches_active` es `None` y no `false` cuando el corpus nunca se
  estampó: nunca-estampado y estampado-con-otra son cosas distintas.

## 5. Tests
- [x] 5.1 `tests/domain/test_business_db_store.py`: la fila activa le gana al
  valor de configuración; sin fila, gana la configuración con origen `default`;
  sin ninguno de los dos, `None` con razón; resolver por default no escribe
  ninguna fila; dos activas para el mismo tenant son imposibles (la base lo
  rechaza). **13 casos**, contra un Postgres real en un esquema descartable y
  con la plomería async a mano sobre `asyncio.run` — la forma del vecino
  (`tests/generation/conversation/test_store.py`) y por lo mismo: un índice
  parcial es comportamiento de la base y un doble en memoria testearía el doble.
  Además: activar retira la anterior y la deja como historial; reactivar una
  retirada reusa su fila; una activación rechazada no mueve la selección
  anterior; `activated_by` se guarda declarado y nunca se inventa; y una activa
  con dos retiradas conviven, porque el índice es parcial.
- [x] 5.2 `tests/api/test_business_db.py`: el listado marca la vigente y su
  origen; activar una corrida sin `loaded_data` da `409`; un `run_id`
  inexistente da `404`; con `BUSINESS_DB_RUN_ID` puesto, activar otra corrida
  **funciona** y pasa a origen `selected`. **11 casos**, con el store stubbeado
  en su costura como hace `test_usage_router.py`: acá se prueba transporte, y
  las reglas del store se prueban contra Postgres en 5.1.
  Las tres corridas del fixture están **copiadas del despliegue** y no
  inventadas, así que no pueden derivar a una forma que el extractor nunca
  produce.
- [x] 5.3 `tests/generation/rag/test_context_budget.py`: el bloque advierte según
  el árbol activo, y cambiar de árbol cambia la advertencia sin tocar la columna
  del chunk. **7 casos nuevos** (23 en el archivo), incluido el inverso —que el
  árbol pueda **borrar** una advertencia estampada de más, que es lo que la
  columna sola no puede hacer— y el del presupuesto contando la advertencia que
  produce el árbol.
- [x] 5.4 Un test que fije que el chunker no queda pegado a una corrida: dos
  resoluciones distintas devuelven chunkers con árboles distintos.
  `tests/test_chunker_is_not_pinned_to_a_run.py`, 5 casos: dos corridas dan dos
  chunkers con árboles que resuelven distinto, la misma corrida devuelve el
  mismo (sigue siendo caché), el mismo `run_id` en dos ambientes son dos
  corridas, y sin corrida se cae al CSV.
- [x] 5.5 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
  Ruff limpio y **947 passed, 0 failed** en la suite completa. **Una sola suite a
  la vez**: correr dos contra el mismo Postgres de Railway agrega fallas que no
  son del código.
  La primera corrida encontró algo que hay que decir: **13 tests de `/answer`
  fallaban con `'NoneType' object has no attribute 'execute'`**. Le pasaban una
  sesión `None` a los routers a propósito —prueban contratos de endpoint, no
  persistencia— y ahora el camino de respuesta resuelve la corrida activa, que es
  una consulta. Se arregló con un fixture `autouse` en `tests/api/conftest.py`
  que stubbea esa costura, igual que ya hacen el del runtime del sintetizador y
  el del ledger. **No** se volvió tolerante el store: un `resolve_active_run` que
  se encogiera de hombros ante una sesión ausente también se tragaría la falla
  real, y «no hay corrida activa» pasaría a ser la respuesta a «la base no
  responde».

## 6. Specs
- [x] 6.1 Delta `specs/extraction-run-selection/spec.md` (capability nueva).
  Ya estaba escrito en el plan y se cumple tal cual. Un requirement se
  reformuló: decía «el servicio no autentica», y eso dejó de ser cierto con
  `add-service-authentication`. Ahora dice lo que sigue en pie y es lo que el
  requirement quería decir: el servicio autentica al **llamador** con un token
  compartido, y un token no es una persona.
- [x] 6.2 Delta `specs/retrieval/spec.md` con el `MODIFIED` que supersede el
  requirement de `add-window-status-metadata`. Se le sumó el escenario del
  fallback a la columna cuando no hay corrida vigente, que la implementación
  hace y el delta no declaraba.
- [x] 6.3 `python scripts/validate_specs.py` sin errores desde la raíz.
  **0 errores y 0 advertencias.**
- [x] 6.4 Sin cambios en `ai-service-standards.md`; sí una fila en
  `app-routes.md` (ver 2.4).

## 7. Dependencias y secuencia
- [x] 7.1 Este change asume `add-window-status-metadata` aterrizado: sale de main
  después de ese PR, no antes. Cumplido: la rama sale de `main` con
  `f1a8b3c92d04` (la migración de `window_status`) como head de Alembic.
- [x] 7.2 `BUSINESS_DB_RUN_ID` se queda como está en el despliegue: pasa a ser el
  default y no bloquea nada. Actualizar su comentario en `app/config.py` y en
  `.env.example` para que diga **valor por defecto**, no pin — el comentario
  actual quedaría afirmando lo contrario de lo que hace el código.
  Los dos reescritos, con la distinción semilla/override explicada y con la
  parte que hay que poder confiar: dejar la variable puesta para siempre no
  bloquea nada y un `activate` nunca se rechaza por ella.
- [ ] 7.3 La pantalla de administración es un change de `web` con
  `/plan-web`, y depende de `add-console-authentication` para el gate de rol.
  **No** se implementa acá. Sigue pendiente a propósito: los endpoints están y
  la pantalla es el próximo change de consola. `app-routes.md` lo dice, para que
  quien lea el inventario no crea que falta un Route Handler por olvido.
  **Queda sin tachar al archivar (2026-09-11), y es deliberado**: nunca fue
  trabajo de este change, así que tacharlo afirmaría que la pantalla existe.
  El change se cierra con este ítem diferido al change de consola, no cumplido.

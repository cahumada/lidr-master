# Implementation Tasks

## 1. Dependencias y secuencia
- [x] 1.1 Este change asume `add-extraction-run-selection` aterrizado en `main`:
  usa `resolve_active_run`, `resolve_navigation_tree(env, run_id)` y las dos
  strings `active_run_id` / `active_run_env` del estado del grafo. La rama sale
  de `main` **después** de ese PR, no antes.
  **Cumplido**: el PR #28 mergeó `add-extraction-run-selection-ai-service` a
  `main` (`b871dc8`), y esta rama lo contiene —
  `app/domain/business_db_store.py` y `app/api/business_db.py` están en el árbol
  de trabajo.
- [x] 1.2 Sin dependencias nuevas. Todo se resuelve con `psycopg`, `pydantic` y
  `tiktoken`, que ya están. Si algo pide una librería nueva, vuelve al proposal.
  **Cumplido**: `pyproject.toml` no ganó paquetes.

## 2. Leer el mirror
- [x] 2.1 `app/generation/rag/business_db/models.py` (nuevo): los tipos que
  viajan — `TableDictionary` (nombre, `description_es`, `description_en`,
  columnas con su descripción), `CatalogRow`, `CodeResolution` (un código anclado
  con su resultado) y `BusinessDbContext` (la corrida, las resoluciones y la
  contabilidad). El vocabulario de resultados es un `Literal` **cerrado**, sin
  `otro`: `resolved`, `not_in_run`, `no_maintained_table`,
  `ng_identi_ignored_by_type`, `table_not_in_dictionary`, `table_not_loaded`,
  `columns_unknown`, `no_validity_mechanism`, `validity_discrepancy`,
  `rows_capped`, `date_unparsed`, `dropped_by_budget`.
- [x] 2.2 `app/generation/rag/navigation.py`: `NavigationTree` carga `NG_IDENTI`
  desde `business_data` y lo expone con `ng_identi(code)`. Va en la estructura en
  memoria y **no** en `NavigationLocation` — ese modelo viaja adentro de la
  metadata de los chunks y agregarle un campo obligaría a otro backfill de 56.537
  filas por un dato que el troceado no usa (`design.md` §9). El loader del CSV no
  lo trae y queda sin resolver, como ya pasa con `SSTATREGT`.
- [x] 2.3 `app/generation/rag/business_db/reader.py` (nuevo): las consultas al
  mirror, **solo lectura**, cacheadas por `(env, run_id, table_name)` con
  `@lru_cache` acotado, siguiendo la forma de `get_navigation_tree_for_run`.
  - `read_table_dictionary` sobre `visualtime.business_tables`.
  - `read_catalog_rows` sobre `visualtime.business_data`, filtrando por
    `(tenant, env, run_id, table_name)` con `LIMIT tope + 1`: el `+1` es cómo se
    detecta que hubo más y se reporta `rows_capped` (`design.md` §8).
  - `read_run_created_at` sobre `visualtime.extraction_runs`, para la fecha de
    referencia por defecto.
  Ninguna consulta escribe nada en `visualtime.*`.
- [x] 2.4 La resolución `NG_IDENTI → TABLE<n>` se aplica **solo al tipo de ventana
  10**. Un `NG_IDENTI ≠ 0` en cualquier otro tipo se ignora y se cuenta como
  `ng_identi_ignored_by_type`. La medición que lo justifica está en §7.1 del
  documento de dominio: de 529 pares de tipo 10 coinciden 440 (83%); de los 11
  pares de otros tipos coinciden 0.

## 3. Vigencia
- [x] 3.1 `app/generation/rag/business_db/validity.py` (nuevo):
  `declared_mechanism(columns)` — una función **pura** sobre las columnas
  declaradas por `business_tables`, que devuelve `status`, `period`, `both` o
  `none`. Nunca una lista de tablas hardcodeada (`design.md` §5).
- [x] 3.2 Los cuatro casos de §4.4 del documento de dominio:
  - solo estado → `SSTATREGT = '1'`, normalizando el `4` a `3` al leer y
    contándolo, como ya hace el árbol.
  - solo período → `DEFFECDATE <= as_of AND (DNULLDATE > as_of OR DNULLDATE IS NULL)`.
  - los dos → los dos, **midiendo y reportando** las filas donde discrepan
    (`validity_discrepancy`). No se decide cuál gana: eso necesita el conteo
    primero y es el punto 3 de §13 del documento de dominio.
  - media pareja o ninguna columna → **sin mecanismo declarado**: no se filtra y
    el bloque lo dice (`no_validity_mechanism`). La presencia de la columna no
    implica el mecanismo — `POLICY`, `CHEQUES` y `BANK_MOV` son la trampa.
- [x] 3.3 `columns = NULL` da `columns_unknown` y `columns = []` no: `NULL` es «no
  se extrajeron columnas» y `[]` es «la tabla no tiene» (§12 del dominio). Sin
  evidencia no se filtra, y se dice.
- [x] 3.4 La fecha de referencia es el `created_at_utc` de la corrida activa, con
  `BUSINESS_DB_CONTEXT_AS_OF` para sobreescribirla. **Nunca `now()`**: un snapshot
  de hace tres meses evaluado contra hoy afirma una vigencia que el dato no
  respalda, y rompe los evals con el reloj de pared (§4.3).
- [x] 3.5 El predicado se evalúa en **Python**, no en SQL: las fechas viven en el
  `jsonb` como texto sin formato declarado, y castear en SQL convierte un valor
  raro en un error de toda la consulta. Una fecha que no parsea se **cuenta**
  (`date_unparsed`) y esa fila queda afuera con su motivo.
- [x] 3.6 **El supuesto de que `1` es `Activo` se mide, no se asume.** Filtrar por
  `SSTATREGT = '1'` se apoya en que §4.1 midió que las 722 `TABLE<n>` usan
  `SSTATREGT` y nada más — pero **el catálogo de estados es por tabla** (§4.2), y
  que todas remitan a `TABLE26` sigue siendo `[HIPÓTESIS]`: `CONFIGECONGROUP`
  declara su propio `1 ACTIVO - 0 DESACTIVO`. Si alguna `TABLE<n>` usa otro
  catálogo, el filtro deja afuera filas vigentes **y la contabilidad de
  completitud no lo ve**, porque desde su punto de vista el filtro funcionó.
  Dos cosas, y la segunda es la que importa:
  - El supuesto queda escrito en `validity.py` con su evidencia, no implícito en
    una comparación con `"1"`.
  - Medirlo: leer la **descripción de la columna** `SSTATREGT` de cada `TABLE<n>`
    en `business_tables` —de ahí salieron las remisiones a *"tabla 26"*, *"1541"*,
    *"535"*— y listar las que declaran otro catálogo o ninguno. El número va
    anotado en esta task. Si la lista no está vacía, esas tablas **no se filtran
    por estado** y se reportan como `no_validity_mechanism`, que es la salida que
    ya existe para «sin mecanismo declarado».
  Es el punto 7 de §13 del documento de dominio, que este change convierte de
  pregunta abierta en riesgo activo.
  **Medido el 2026-09-11** sobre `20260909_214921` / `life_seguros` / `PROD`,
  las 722 `TABLE<n>` de `business_tables`:
  - 137 remiten a TABLE26.
  - **4 catálogos ajenos** (no se filtran por estado; `no_validity_mechanism`):
    `TABLE1520` (tabla 1520), `TABLE1535` (tabla 535), `TABLE1536` (tabla 1541),
    `TABLE9150` (TABLE9150).
  - 573 genéricos («Estado del registro.») — se filtran con la hipótesis TABLE26.
  - 8 sin columna `SSTATREGT` en el diccionario.
  Entre las `TABLE<n>` que ancla el tipo 10 de esa corrida: 100 TABLE26, 1 ajena
  (`TABLE9150`), 422 genéricas, 74 sin entrada en el diccionario.

## 4. El bloque y su presupuesto
- [x] 4.1 `app/generation/rag/business_db/render.py` (nuevo): `render_block`, el
  **único** renderer del bloque — lo que se mide es lo que se manda, igual que
  `render_hit_block`. Encabezado con la corrida y el ambiente, un bloque por
  código anclado, y el cierre de completitud.
- [x] 4.2 El bloque se rotula como **otra autoridad**: dice que no es
  documentación funcional sino lo que la base declara hoy, y que ante una
  diferencia con la especificación hay que reportarla y no elegir una. Es §10 del
  dominio, y va **adentro** del bloque, no al lado (misma razón que
  `render_limits` del CAG).
- [x] 4.3 Presupuesto: `BUSINESS_DB_CONTEXT_MAX_TOKENS`, cobrado **adentro** de
  `ANSWER_MAX_CONTEXT_TOKENS` y nunca encima. Se cuenta con `count_tokens()`, el
  mismo tokenizer que el resto.
- [x] 4.4 `DROP_ORDER = ("rows_tail", "column_descriptions", "table_description")`.
  La declaración de la ventana no se recorta nunca. Las filas se recortan desde la
  cola y **enteras** — media fila es un valor de catálogo truncado que se lee como
  completo — y la lista recortada se rotula con su conteo real («23 vigentes, se
  muestran 10»).
- [x] 4.5 Todo lo recortado por presupuesto entra en la contabilidad como
  `dropped_by_budget`, con sus conteos. Nada se recorta en silencio.

## 5. El camino de respuesta
- [x] 5.1 `app/dependencies.py`: `resolve_business_db_context(env, run_id, codes)`,
  al lado de `resolve_navigation_tree` y con la misma forma — sincrónico y
  cacheado por corrida (`design.md` §7). Los dos caminos de respuesta usan **esta**
  función, no dos lecturas paralelas.
- [x] 5.2 Los códigos anclados son los `document_id` de los hits que **entraron al
  prompt** (`budgeted.kept`), deduplicados y acotados por
  `BUSINESS_DB_CONTEXT_MAX_CODES`. Un hit que no llegó al prompt no ancla nada:
  el bloque describe lo que la respuesta puede citar.
- [x] 5.3 `app/foundation/prompts/answer/v3/{system,user}.j2` (nuevos), copiados de
  `v2` más el bloque. `v1` y `v2` quedan **congelados** y byte a byte
  (`design.md` §3).
- [x] 5.4 `app/generation/rag/prompt_builder.py`: `PROMPT_VERSION_WITH_BUSINESS_DB
  = "v3"` y el orden de ajuste **evidencia → memoria → base**, dentro de
  `build_budgeted_messages` para que ningún call site lo pueda equivocar de a uno
  — el mismo argumento por el que el orden evidencia/memoria ya vive ahí.
- [x] 5.5 `app/generation/rag/answer.py` (camino directo) y
  `app/domain/graph/agents/answer_synthesizer.py` (camino agéntico). En el grafo
  la corrida ya viaja como `active_run_id` / `active_run_env`: se usa esa y no se
  vuelve a resolver, para que un turno pausado en el gate y retomado después de
  una activación siga respondiendo con la corrida en la que empezó.
- [x] 5.6 Sin corrida activa **no hay bloque**, y la respuesta dice por qué. No se
  cae a la corrida más reciente ni al CSV (`design.md` §10).

## 6. Contabilidad de completitud
- [x] 6.1 `BusinessDbContext.complete: bool` con la definición de `design.md` §6:
  **no** es incompletitud que la base declare que no hay nada que traer
  (`no_maintained_table`, `ng_identi_ignored_by_type`); **sí** lo es que hubiera
  algo y no llegara (`table_not_in_dictionary`, `table_not_loaded`, `rows_capped`,
  `columns_unknown`, `date_unparsed`, `dropped_by_budget`).
- [x] 6.2 La contabilidad viaja en `AnswerResponse.business_db`
  (`app/generation/rag/schemas.py`), al lado de `context_truncated` y
  `dropped_hits` y por la misma razón.
- [x] 6.3 **Y en prosa adentro del bloque**, con la sección «Qué no se pudo traer»
  y una línea por causa. Tiene dos lectores: quien audita y el modelo, que es
  quien no tiene que afirmar que un catálogo está completo.
- [x] 6.4 Un log estructurado por resolución con sus conteos, para poder medir la
  cobertura real del ancla sin instrumentar a mano.
  **Cumplido**: evento `business_db_resolution` por código.

## 7. Configuración
- [x] 7.1 `app/config.py` y `.env.example`: `BUSINESS_DB_CONTEXT_ENABLED`
  (default `true`), `BUSINESS_DB_CONTEXT_MAX_TOKENS`,
  `BUSINESS_DB_CONTEXT_MAX_ROWS`, `BUSINESS_DB_CONTEXT_MAX_CODES`,
  `BUSINESS_DB_CONTEXT_AS_OF` (vacío = el `created_at_utc` de la corrida activa).
  Cada uno con su comentario bilingüe explicando qué pasa con el valor límite —
  un `0` no significa «sin límite».
- [x] 7.2 El flag existe para el eval, no como interruptor de emergencia: una
  corrida con bloque y una sin él son dos prompts distintos y el eval tiene que
  poder correr las dos. Decirlo en el comentario, o el próximo lector lo va a
  tratar como un kill switch y a dejarlo apagado.

## 8. Tests
- [x] 8.1 `tests/generation/rag/business_db/test_validity.py`: los cuatro casos de
  §4.4 sobre columnas declaradas; media pareja da `no_validity_mechanism` y no un
  predicado a medias; `columns = NULL` y `columns = []` no se confunden; el `4` de
  `SSTATREGT` se normaliza a `3` y se cuenta; una fecha que no parsea cuenta y no
  rompe; `as_of` explícito le gana al `created_at_utc` de la corrida.
- [x] 8.2 `tests/generation/rag/business_db/test_reader.py`: contra Postgres real
  en un esquema descartable, como hace `tests/domain/test_business_db_store.py` —
  acá se prueba SQL sobre `jsonb`, y un doble en memoria probaría el doble. El
  `LIMIT tope + 1` detecta el desborde; una tabla sin filas para la corrida da
  `table_not_loaded` y no una lista vacía indistinguible.
- [x] 8.3 `tests/generation/rag/business_db/test_render.py`: el bloque dice de qué
  corrida habla; el `DROP_ORDER` recorta en ese orden; una lista recortada lleva su
  conteo real; el bloque nunca parte una fila al medio; la sección «qué no se pudo
  traer» aparece con cada causa.
- [x] 8.4 `tests/generation/rag/business_db/test_completeness.py`: `complete` es
  `true` cuando la base declara que no hay nada que traer, y `false` en cada una de
  las seis causas del otro grupo. Un caso por causa — el vocabulario es cerrado y
  el test es lo que lo mantiene cerrado.
- [x] 8.5 `tests/generation/rag/test_prompt_builder.py`: `v3` sin bloque de base
  rinde el mismo texto que `v2` (el test que detecta que alguien editó uno y no el
  otro); con bloque, el orden de ajuste es evidencia → memoria → base; el bloque de
  base nunca le saca presupuesto a un chunk ni a un turno de memoria.
- [x] 8.6 `tests/generation/rag/test_navigation.py`: `ng_identi` se carga del
  mirror y queda sin resolver desde el CSV; `NavigationLocation` **no** gana campos
  — un test que lo fije, porque el defecto sería invisible hasta el próximo
  backfill.
- [x] 8.7 `tests/api/test_answer_router.py`: `business_db` viaja en la respuesta;
  sin corrida activa el campo dice por qué y no hay bloque. Con el reader
  stubbeado en `tests/api/conftest.py`, como hace `test_usage_router.py`.
- [x] 8.8 Una verificación **contra el mirror real** de la corrida `20260909_214921`
  (`life_seguros` / `PROD`), anotada en esta task con los números que dé: un código
  de tipo 10 que resuelve a su `TABLE<n>` con filas vigentes, uno de otro tipo con
  `NG_IDENTI ≠ 0` que se ignora, y uno cuya tabla no está cargada. Los tres casos
  existen en esa corrida; si alguno no aparece, eso es un hallazgo y va anotado.
  **Medido el 2026-09-11** (los tres casos existen; no es hallazgo):
  - Tipo 10: `MA0007` → `TABLE7`, `rows_valid=50` (tope 50, `rows_capped`).
  - Otro tipo: `COL504` (tipo 3, `NG_IDENTI=2`) → `ng_identi_ignored_by_type`.
  - Sin tabla: `MA0005` → `TABLE5` → `table_not_in_dictionary` (el primer
    hueco de esta corrida es diccionario, no filas vacías).
- [x] 8.9 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
  Una sola suite a la vez contra el Postgres de Railway.
  **2026-09-11**: `1006 passed` (659 s); `ruff check .` sin hallazgos.

## 9. Specs
- [x] 9.1 Delta `specs/business-db-context/spec.md` (capability nueva).
- [x] 9.2 Delta `specs/answer-generation/spec.md`: `MODIFIED` del requirement del
  prompt (la versión `v3` y el bloque subordinado) y del requirement del techo de
  contexto (tres bloques con orden fijo, todos adentro del mismo techo).
- [x] 9.3 `python scripts/validate_specs.py` sin errores desde la raíz.
  **2026-09-11**: 20 specs, 4 domain, 1 change, 57 archived — 0 errores.
- [x] 9.4 Sin cambios en `app-routes.md`: este change no agrega ninguna ruta. Si
  al implementar aparece una, es señal de que el alcance se corrió.
- [ ] 9.5 Anotar en `openspec/domain/visualtime-database-metadata.md` §13 qué
  huecos cierra este change y cuáles siguen abiertos. **No** convertir nada de
  `domain/` en requirement: sigue siendo referencia.
  **Primera mitad hecha el 2026-09-11, antes de implementar**, y anotada como tal:
  §13 dice qué huecos toca este change —el 3 recibe su insumo, el 2 deja de ser
  invisible, el 7 pasa a ser riesgo activo, el 4 y el 6 quedan fuera a propósito—
  bajo el título **«En curso … todavía sin implementar»** y no bajo «Cerrado por».
  Escribir «cerrado» antes de que el código exista es exactamente la forma en que
  una fuente de referencia empieza a mentir.
  **Falta la segunda mitad**: al archivar, mover lo que efectivamente quedó hecho
  a un bloque «Cerrado por `add-business-db-context`» con los números medidos, y
  dejar en «en curso» solo lo que siga sin estarlo. Esta task se tacha ahí, no antes.

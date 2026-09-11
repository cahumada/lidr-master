# Diseño

Todas las cifras salen de la corrida activa `20260909_214921` del mirror, contra
los 2.176 documentos del corpus cargado.

## 1. Por qué batch y no lectura por request

El primer salto —`document_id` contenido en el nombre del objeto Oracle— es un
`LIKE '%CODE%'`. El comodín **inicial** hace que ningún índice B-tree sirva:
Postgres recorre los 10.988 nombres de rutina de la corrida. Por request, con
cinco a diez códigos anclados, son diez recorridos completos antes de empezar a
resolver tablas.

Pero el argumento decisivo no es el costo, es la **corrección**. La
desambiguación por munch máximo (§2) necesita saber si existe un código más largo
que también matchea esa rutina, y eso exige el universo entero de `document_id`.
En un request solo están los códigos de los hits: `CA013` llegaría solo, sin
`CA013A` a la vista, y se llevaría `INSPOSTCA013A` sin que nada lo delate. **La
misma entrada daría distinta salida según con qué otros hits salió** — exactamente
el defecto que la fusión por RRF evita en `retrieval`.

El precedente está en el repo: `build_process_map.py` arma el grafo y persiste
`process_map_edges` para que la recuperación expanda por ellas sin recomputar. El
comentario de ese modelo lo dice — "el mismo dato, cada uno en la forma que su
consumidor necesita". `transaction_table_edges` es la misma decisión.

**Identidad de la arista:** `(tenant, env, run_id, transaction_code, table_name)`.
Va por `run_id` del mirror y **no** por `doc_version`, a diferencia de
`process_map_edges`: lo que la arista afirma es qué declaró Oracle en esa corrida.
Activar otra corrida tiene que poder traer otras aristas.

### Alternativa descartada: resolver con `pg_trgm`

Un índice GIN de trigramas haría indexable el `LIKE '%CODE%'`. Pierde igual: no
resuelve la ambigüedad, agrega una extensión y un índice sobre una tabla del
mirror —que es de otro repo y se recarga entera por upsert— y deja la latencia
del segundo salto adentro del request de respuesta.

## 2. Munch máximo: el código más largo se queda con la rutina

Medido: **184 `document_id` de largo ≥ 5 son substring de otro `document_id`**.
Las familias son tres y todas reales:

| forma | ejemplo | de quién es la rutina |
|---|---|---|
| sufijo de variante | `CA013` ⊂ `CA013A`, `CA017` ⊂ `CA017A`, `CA028` ⊂ `CA028_1` | de la variante |
| solicitud de clave | `AG001` ⊂ `AG001_K`, `BC003` ⊂ `BC003_K` | de la solicitud |
| prefijo de módulo | `AG001` ⊂ `MAG001`, `AM002` ⊂ `MAM002` | del mantenimiento |

El impacto real es chico y concreto: **55 pares código–rutina ambiguos sobre 31
documentos**. `INSPOSTCA013A`, `INSVALCA017A`, `INSREARECEIPT_CA028_1PKG` hoy le
colgarían sus tablas al código corto.

La regla: para cada nombre de rutina se toma **el código matcheante más largo**, y
solo ese se lleva la arista. No es un desempate heurístico — `INSPOSTCA013A`
nombra a `CA013A` de manera inequívoca, y que `CA013` sea prefijo suyo es un
accidente de la nomenclatura.

Lo que **no** hace la regla: inventar la arista del lado del código corto. Si
`CA013` no tiene ninguna rutina propia, queda con `no_dependency_routine` — que es
un hecho declarado, no un vacío.

**La guarda de largo ≥ 5 se mantiene** (§5.3 del dominio): los de largo 4 dan
`LOGO → INSCOPYCATALOGO` y `MENU → REAWINDOWSMENUPKG`, falsos positivos puros. Un
código de largo 4 no ancla y se cuenta como `code_too_short_to_anchor`.

## 3. El rol sale de reglas ordenadas, no de un LLM ni del texto del chunk

Tres razones para que sea una tabla de datos `(patrón, rol)` recorrida en orden,
como `taxonomy.py`:

1. **Es auditable.** Cuando aparezca el contraejemplo —y va a aparecer— se edita
   una fila, no una rama de código.
2. **Es barata.** Corre en el batch, sobre 49.271 aristas, sin una llamada a un
   modelo.
3. **Es honesta.** Un LLM clasificando devuelve siempre una etiqueta. Una regla
   ordenada devuelve `unknown` cuando ninguna aplica, y esa distinción es la que
   hace que el bloque pueda decir *"no sé qué rol tiene `NOPAYROLL` para `CA014`"*
   en vez de afirmarlo.

### 3.1 Las señales, en orden de autoridad

Las señales del **destino** ganan a las del **camino**, porque describen qué es la
tabla y no cómo se llegó a ella.

| # | señal | fuente | rol |
|---:|---|---|---|
| 1 | nombre `TABLE<n>`, o descripción que contiene *(Contenido fijo)* | `business_tables` | `reference` |
| 2 | `MESSAGE`, `WIN_MESSAG` | `business_tables` | `message` |
| 3 | sufijo `_HIS`, o descripción que empieza con *Historia* | `business_tables` | `historical` |
| 4 | alcanzada **solo** por rutinas `INSVAL*` | prefijo de rutina | `validation` |
| 5 | fan-in global por encima del umbral | grafo completo | `reference` |
| 6 | alcanzada por rutinas de escritura (`INSPOST*`, `INSPRE*`, `INSEXECUTE*`, `INS*`) **y** por `REA*` | prefijo de rutina | `core` |
| 7 | nada de lo anterior | — | `unknown` con su razón |

Verificación sobre el caso que el dueño anotó: `CA014` alcanza `COVER` por
`INSCA014PKG`, `INSPOSTCA014`, `INSVALCA014DB02` **y** `REACA014` — las cuatro
fases, regla 6 → `core`. Alcanza `NOPAYROLL` solo por `INSVALCA014DB02` y
`INSVALCA014DB03` — regla 4 → `validation`. Y alcanza `POLICY_HIS` por el sufijo
— regla 3 → `historical`.

### 3.2 El fan-in es desempate, y no afirma nada solo

`CERTIFICAT` aparece en 1.910 rutinas, `CLIENT` en 1.861, `POLICY` en 1.738. Con
ese fan-in, que una transacción cualquiera las toque no informa: las toca casi
todo el sistema. En el otro extremo, **1.045 de las 1.906 tablas tienen fan-in ≤
5** y ahí tocar sí informa.

La regla 5 está **después** de las señales del destino y **antes** de `core` a
propósito: evita que `CLIENT` se declare core de `CA025` solo por aparecer en sus
cuatro fases. Pero el umbral es un parámetro con default medido, no una constante
mágica, y la arista guarda su fan-in para que la decisión se pueda revisar sin
reconstruir.

**Lo que el fan-in no dice:** que la tabla sea poco importante. Dice que es
transversal. Por eso emite `reference` y no un descarte.

### 3.3 `unknown` va a ser común, y está bien

Sobre las 1.345 rutinas ancladas: 490 `REA*`, 132 `INSPOST*`, 65 `INSVAL*`, 27
`INSPRE*`, 3 `INSEXECUTE*`, 2 `INSCOPY*` — y **481 con el prefijo genérico `INS`
más 145 sin prefijo conocido**. Casi la mitad del camino no se clasifica por su
nombre.

Una tabla alcanzada solo por rutinas de ese grupo llega a la regla 7. El bloque la
emite con rol `unknown` y la causa `role_unknown`, y el prompt instruye tratarla
como *"la transacción la toca, no sé en qué carácter"*. Es menos de lo que
querríamos y más de lo que hay hoy, que es nada.

## 4. Por qué se mide antes de enchufarlo al prompt

El recall ya está verificado sobre las cuatro transacciones anotadas: las tablas
que el dueño nombró salen todas. Lo que **no** está medido es la precisión de
`core`, que es lo único que decide si el bloque ayuda o estorba: con mediana 8 y
p90 22 tablas por código, un `core` mal asignado pone la tabla equivocada primero
en un bloque que el modelo lee como autoridad.

Por eso el eval es una tarea del change y no un extra: `evals/golden_transaction_tables.json`
con ~20 transacciones anotadas por el dueño, y `eval_transaction_tables.py`
reportando precisión y recall de `core` y la tasa de `unknown`. El precedente es
`eval_retrieval.py` sobre el golden set de 35 preguntas.

**Sin ese número el bloque queda detrás de su flag, apagado.** Es lo mismo que
hizo `add-business-db-context` con el bloque entero.

## 5. Por qué una sección dentro de `v3` y no una versión `v4`

`business-db-context` ya gobierna qué dice el bloque de base: que es otra
autoridad, que declara lo que no pudo traer, y en qué orden se recorta. Las tablas
por dependencia son **más contenido de ese bloque**, no otro bloque ni otra
autoridad. Una `v4` duplicaría las plantillas para agregar una sección.

Lo que sí cambia es el orden de recorte, y se declara acá porque el orden de
`add-business-db-context` (filas → descripciones de columna → descripción de
tabla) no contemplaba esta sección:

1. tablas con rol `unknown`, desde la cola
2. tablas con rol `reference`
3. filas de catálogo, desde la cola *(orden existente)*
4. descripciones de columna *(orden existente)*
5. descripción de tabla *(orden existente)*

`core`, `historical`, `validation` y `message` **no se recortan**, y la lista de
rutinas que justifica cada arista tampoco: sin ella la tabla deja de ser citable y
pasa a ser una afirmación sin origen. Si el techo no alcanza ni para eso, se
recorta el código entero y se cuenta como `dropped_by_budget`, que ya existe.

## 6. `edges_not_built` es la causa que importa operativamente

`add-extraction-run-selection` dejó activar una corrida desde la consola. Nada
garantiza que el batch haya corrido para esa corrida: un administrador activa
`20260910_…`, las aristas son de `20260909_…`, y el bloque queda mudo sobre las
tablas sin que nadie sepa por qué.

La causa `edges_not_built` cierra eso en tres lugares a la vez: la resolución la
lleva, el bloque la nombra, y `/business-db` la muestra **antes** de activar (§7).
Marcada como incompletitud, no como ausencia declarada: había algo y no llegó.

## 7. Por qué la consola es parte de este change y no del siguiente

Hoy `AnswerResponse.business_db` viaja y muere: `lib/ai-service/types.ts` no tiene
el campo. Mientras el bloque era el catálogo de una `TABLE<n>`, mostrarlo era una
mejora. Con la cadena `código → rutinas → tablas` deja de serlo, por dos motivos
que el repo ya trata como requisito:

- **Es la procedencia.** `web-console` ya exige que la pantalla de búsqueda exponga
  de dónde salió cada resultado, y `retrieval` que cada hit diga por qué camino
  entró. Una tabla afirmada en la respuesta sin poder ver qué rutina la justifica
  es el mismo defecto, en la otra autoridad.
- **Es la única forma de ver un `unknown`.** El diseño acepta a propósito que
  buena parte del camino no se clasifique. Si eso no es visible, el operador lee
  el bloque como si estuviera completo — que es exactamente lo que
  `add-business-db-context` se propuso evitar.

`/agents/flow` entra porque esa pantalla declara *cómo resuelve el servicio*, y a
partir de este change la resolución tiene un paso que el diagrama no nombra. La
spec de esa pantalla ya prohíbe declarar nodos en TypeScript: el paso sale del
servicio, en `GET /config`, o no se dibuja.

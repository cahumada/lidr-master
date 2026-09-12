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

### 3.1 No hay rol `core`: la regla que el plan proponía corre al revés

El plan iba a derivar `core` de un fan-in global bajo. **Medido contra las cuatro
transacciones que el dueño anotó, esa regla está invertida:**

| código | tabla anotada | fan-in | tabla NO anotada | fan-in |
|---|---|---:|---|---:|
| `CA014` | `COVER` | 1.037 | `NOPAYROLL` | 44 |
| `CA025` | `CLIENT` | 1.925 | `CLIALLOPRO` | 42 |
| `CA025` | `ROLES` | 1.004 | `TAB_COVROL` | 146 |
| `CA001` | `CERTIFICAT` | 1.989 | `CUR_ALLOW` | 30 |

Tiene sentido en retrospectiva: una póliza, un certificado y un cliente los toca
casi toda rutina del sistema **porque** son las entidades centrales del negocio.
La rareza indica periférico, no central.

Tampoco hay otra señal declarada que los aísle. El tipo de rutina los rankea
alto pero no los separa: en `CA001`, `CERTIFICAT` (anotada) y `ROLES` (no
anotada) tienen la misma firma `ins?,read` y cobertura 0,50 contra 0,30. Y la
cobertura sola deja empates —en `CA048`, `PREMIUM` (no anotada) empata 1,00 con
`CERTIFICAT` y `POLICY_HIS` (anotadas).

**Decisión:** no se emite `core`. Se emiten los roles que el diccionario declara
—`reference`, `historical`, `message`— más `validation` cuando solo la alcanzan
rutinas de validación, y todo lo demás queda `unknown` con su razón. Afirmar
`core` sobre cuatro puntos anotados sería la calibración manual que `retrieval`
evita a propósito con RRF.

El fan-in **se guarda igual en cada arista**: revisarlo cuando el set anotado
llegue a 20 casos no puede exigir reconstruir 5.907 aristas.

### 3.2 Las señales, en orden de autoridad

Las señales del **destino** ganan a las del **camino**, porque describen qué es la
tabla y no cómo se llegó a ella.

| # | señal | fuente | rol |
|---:|---|---|---|
| 1 | nombre `TABLE<n>` | nombre | `reference` |
| 2 | descripción con *(Contenido fijo)* | `business_tables` | `reference` |
| 3 | `MESSAGE`, `WIN_MESSAG` | nombre | `message` |
| 4 | sufijo `_HIS` | nombre | `historical` |
| 5 | descripción que empieza con *Historia* | `business_tables` | `historical` |
| 6 | alcanzada **solo** por rutinas `INSVAL*` | prefijo de rutina | `validation` |
| 7 | nada de lo anterior | — | `unknown` con su razón |

Verificado sobre el caso anotado: `CA014` alcanza `NOPAYROLL` solo por
`INSVALCA014DB02` y `INSVALCA014DB03` — regla 6 → `validation`. Alcanza
`POLICY_HIS` por el sufijo — regla 4 → `historical`. Y alcanza `COVER` por las
cuatro clases de rutina, sin que ninguna regla aplique — regla 7 → `unknown`.

### 3.3 El orden es la cobertura, y son dos conteos declarados

Sin `core`, hace falta otra cosa que decida qué va arriba. Es la **cobertura**:
cuántas rutinas de la transacción llegan a la tabla, sobre cuántas tiene. `COVER`
es 3/3 para `CA014`; `NOPAYROLL`, 2/3.

Es el mismo criterio que hace aceptable a RRF: dos conteos declarados divididos,
sin umbral que elegir. Un orden malo es entonces un hecho sobre el grafo y no un
peso mal puesto. El bloque lo dice explícitamente —*"el orden es por cuántas
rutinas de la transacción llegan a cada una; no es una jerarquía de importancia
declarada"*— para que el modelo no lea el primer puesto como una afirmación.

### 3.4 `unknown` es la mayoría, y está bien

Construido contra la corrida activa: **4.939 de 5.907 aristas (84%) quedan
`unknown`**, contra 645 `reference`, 167 `validation`, 139 `historical` y 17
`message`.

Es mucho, y es el número honesto: 481 de las rutinas ancladas llevan el prefijo
genérico `INS` y 145 no llevan ninguno conocido. El bloque cierra la sección
diciendo *"la transacción toca la tabla, pero en qué carácter no está declarado.
No lo supongas."* Es menos de lo que querríamos y más de lo que hay hoy, que es
nada.

## 4. Por qué se mide antes de enchufarlo al prompt

El recall del grafo ya está verificado sobre las cuatro transacciones anotadas:
las tablas que el dueño nombró salen todas. Lo que **no** está medido es si
sobreviven al tope del bloque, que es lo único que decide si la respuesta las
puede citar: con mediana 8 y máximo 185 tablas por código, una tabla recortada
es una tabla que la respuesta no tiene.

Por eso el eval mide **recall@N** y no precisión de `core` —que no existe—:
`evals/golden_transaction_tables.json` con ~20 transacciones anotadas por el
dueño, y `eval_transaction_tables.py` reportando cuántas anotadas sobreviven al
tope, en qué posición las deja la cobertura, y qué proporción del bloque sale
`unknown`. El precedente es `eval_retrieval.py` sobre el golden set de 35
preguntas.

**Sin 20 casos anotados y 90% de recall el bloque queda detrás de su flag,
apagado.** El umbral vive en el script, no en un comentario. Hoy el set tiene
los 4 de la semilla, así que el flag arranca en `false`.

## 5. Por qué una sección dentro de `v3` y no una versión `v4`

`business-db-context` ya gobierna qué dice el bloque de base: que es otra
autoridad, que declara lo que no pudo traer, y en qué orden se recorta. Las tablas
por dependencia son **más contenido de ese bloque**, no otro bloque ni otra
autoridad. Una `v4` duplicaría las plantillas para agregar una sección.

Lo que sí cambia es el orden de recorte, y se declara acá porque el orden de
`add-business-db-context` (filas → descripciones de columna → descripción de
tabla) no contemplaba esta sección:

1. tablas, desde la cola del orden por cobertura
2. filas de catálogo, desde la cola *(orden existente)*
3. descripciones de columna *(orden existente)*
4. descripción de la tabla *(orden existente)*

Sin `core` que proteger, **la cobertura es la protección**: se recorta la tabla
que menos rutinas de la transacción tocan, y la mejor cubierta sobrevive. Hay un
piso de una tabla por código: un código que quedara sin ninguna se leería como
*"no toca tablas"*, que es un hecho distinto y ya tiene su propia causa.

La lista de rutinas que justifica cada tabla **no se recorta nunca**: sin ella la
tabla deja de ser citable y pasa a ser una afirmación sin origen. Si el techo no
alcanza ni para eso, se recorta el código entero con `dropped_by_budget`, que ya
existe.

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

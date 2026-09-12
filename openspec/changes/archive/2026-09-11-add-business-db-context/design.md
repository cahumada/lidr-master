# Diseño

## 1. Por qué el ancla son los códigos de los hits y no las entidades de la pregunta

Las dos opciones resuelven preguntas distintas, y una tiene un problema abierto.

Anclar por los `document_id` de los hits usa un dato **declarado**: el código de
transacción ya está en el chunk, ya es la clave con la que el árbol de navegación
resuelve el breadcrumb, y `WINDOWS.SCODISPL` es la misma columna. No hay nada que
inferir, no hay una segunda llamada a un modelo, y el resultado es reproducible
entre corridas de eval — que es la condición para poder medir si el bloque mejora
las respuestas.

Anclar por entidades de la pregunta ("¿qué bancos hay cargados?" → `TABLE7`)
cubre algo que esto no: las ~655 transacciones activas sin documento, donde no va
a haber hit que anclar. Es la pregunta más valiosa y la que tiene el problema
abierto — reconocer un nombre de tabla en prosa castellana, con el hueco de
medición de §5.2 todavía sin cerrar. Se difiere entera, no se hace a medias.

Consecuencia honesta y declarada: **este change no le habla a las transacciones
sin documento**. Sirve para enriquecer lo que ya se recupera, no para llegar
adonde la recuperación no llega.

## 2. Por qué un bloque propio y no una anotación adentro del bloque del hit

§10 del documento de dominio dice que corpus y base son dos autoridades y que
cuando difieren **no hay un error a resolver, hay un hallazgo a reportar**. Un
bloque de evidencia que mezclara las dos borraría esa distinción justo donde más
importa: el modelo leería "la especificación dice X" y "la base dice Y" como una
sola fuente y elegiría una — casi siempre la que aparece primero.

La advertencia de `window_status` sí va adentro del bloque del hit, y no es
incoherente: eso es un **adjetivo sobre el chunk** ("esto describe una transacción
que el sistema no contempla"), no una afirmación sobre otra cosa. El diccionario y
las filas son contenido nuevo, con su propia procedencia y su propia corrida.

## 3. Por qué `v3` lleva los dos bloques opcionales y no hay matriz de versiones

Con dos bloques opcionales —memoria y base— las combinaciones son cuatro, y
versionar cada una (`v2` memoria, `v3` base, `v4` las dos) haría que agregar un
tercer bloque opcional costara cuatro versiones más.

La regla que se adopta: **`v1` y `v2` quedan congelados** y siguen renderizando
byte a byte para una corrida sin bloque de base — que es lo que mantiene
comparables los evals ya corridos —, y `v3` es la versión que lleva base y, si
hay, memoria. Una corrida con memoria y sin base sigue siendo `v2`; una con base
es `v3` tenga memoria o no.

Costo aceptado: `v2` y `v3` sin base no serían byte a byte idénticos si algún día
divergen. Por eso `v3` se crea copiando `v2` y agregando el bloque, y hay un test
que fija que `v3` sin bloque de base rinde el mismo texto que `v2` — si alguien
edita uno y no el otro, se entera ahí.

## 4. El orden de ajuste: evidencia → memoria → base

El invariante que ya existe es *"la memoria nunca le saca presupuesto a un
chunk"*. El bloque nuevo se mete abajo de los dos, y no es arbitrario:

- Un chunk desplazado cuesta una cita. Es lo más caro.
- Un turno de memoria desplazado rompe el hilo de una conversación multi-turno,
  que es un fallo que el usuario ve de inmediato.
- Un renglón de diccionario desplazado cuesta enriquecimiento, y —a diferencia de
  los otros dos— **el bloque puede decir que lo perdió**. Esa es la razón real del
  orden: es el único de los tres cuyo recorte se puede declarar adentro del propio
  bloque, así que es el único que puede recortarse sin volverse invisible.

Alternativa descartada: darle al bloque de base un presupuesto **encima** de
`ANSWER_MAX_CONTEXT_TOKENS`. Convertiría un techo en una sugerencia y el desborde
lo descubriría el proveedor, que es exactamente lo que `context_budget.py` existe
para evitar.

### 4.1 Qué se recorta primero adentro del bloque

`DROP_ORDER = ("rows_tail", "column_descriptions", "table_description")`, y la
declaración de la ventana (código, descripción, tipo, estado) **no se recorta
nunca**: son dos renglones por código y es lo único que un RAG no puede
reconstruir por similitud.

Las filas se recortan **desde la cola y enteras**, igual que los chunks. Media
fila es un valor de catálogo truncado que se lee como uno completo, y en una base
de seguros eso es peor que una fila menos. Y una lista recortada se rotula con su
conteo real —*"23 filas vigentes, se muestran 10"*— porque una lista que no dice
que está cortada se lee como el catálogo entero.

## 5. El mecanismo de vigencia se lee de la tabla, nunca se hardcodea

§4.1 midió la distribución sobre 1.492 tablas y §4.4 fijó la regla por caso. La
tentación es traducir esa medición a una lista en código (*"estas 879 usan
`SSTATREGT`"*). No se hace, por dos razones:

1. La medición es de **una corrida**. Una lista en código quedaría afirmando sobre
   corridas futuras algo que nadie midió, y el extractor tiene su propio ciclo.
2. `business_tables.columns` **ya declara** qué columnas tiene cada tabla. Derivar
   el mecanismo de ahí es leer el dato en vez de recordarlo.

Los cuatro casos de §4.4 se implementan como una función pura sobre la lista de
columnas declaradas, y la trampa de §4.1 queda respetada sin esfuerzo: **la
presencia de la columna no implica el mecanismo**, así que media pareja da
`no_validity_mechanism` y no un predicado que ni siquiera cierra.

`columns = NULL` y `columns = []` no son lo mismo (§12): `NULL` es *no se
extrajeron columnas* y da `columns_unknown` — sin evidencia, no se filtra y se
dice. `[]` es *la tabla no tiene columnas*, que para una tabla de catálogo es un
dato de por sí.

Y el `4` de `SSTATREGT` se normaliza a `3` al leer, como ya hace el árbol, con su
contador: §4.2 lo declara error de datos y son 18 filas en `WINDOWS`. Si una
corrida futura trae más, el contador lo dice en vez de normalizarlo en silencio.

## 6. Por qué la completitud es un vocabulario cerrado y no prosa

El pedido fue *"¿se recuperó todo lo posible o quedaron cosas por recuperar?"*. Un
booleano solo sirve si está definido, y definirlo obliga a separar dos cosas que
se parecen:

- **No hay nada que traer** — la transacción no es de tipo 10 y no declara tabla
  que mantenga; el `NG_IDENTI` de otro tipo se ignora por la regla de §7.1. Eso
  **no** es incompletitud: la base declaró que no hay, y se trajo todo lo que hay.
- **Había algo y no llegó** — la tabla no está en el diccionario (los 74 pares de
  §7.1 que apuntan a una `TABLE<n>` inexistente), no está cargada en
  `business_data` (las ~143 de la allowlist incompleta, §13.2), se pasó del tope
  de filas, o la recortó el presupuesto. Eso **sí** lo es.

`complete` es *no hubo ningún resultado del segundo grupo*. El vocabulario es
cerrado y sin `otro`: una causa que no esté enumerada tiene que agregarse al
vocabulario, que es la forma de que no aparezca un `complete = false` sin
explicación. La regla de oro del repo aplicada tal cual — nunca borrar información
de negocio en silencio.

Y va en dos lugares, porque tiene dos lectores: en `AnswerResponse.business_db`
para quien opera y audita, y **en prosa adentro del bloque** para el modelo, que
es quien tiene que no afirmar que un catálogo está completo. Es la misma
prevención que `render_limits` del CAG: *un modelo que reciba el mapa sin sus
límites va a contestar que una transacción no existe*.

## 7. Lectura sincrónica y cacheada, como el árbol

`add-extraction-run-selection` ya fijó la forma: la corrida viaja en el estado del
grafo como dos strings y el árbol se trae con `resolve_navigation_tree(env,
run_id)`, un loader **sincrónico y cacheado** por corrida. El lector del mirror
sigue ese patrón y no inventa uno segundo: cache por `(env, run_id, table_name)`.

Por qué no la `AsyncSession` del request: el sintetizador del grafo no la tiene
—corre donde no hay request—, y resolver eso significaría enhebrar una sesión por
todo el grafo o tener dos caminos de lectura. Dos caminos es cómo el camino
directo y el agéntico empiezan a no coincidir sobre qué dice la base, que es la
misma clase de defecto que `_decide` evitó para la precedencia de la corrida.

El costo es I/O bloqueante en un request async la primera vez que se toca una
tabla. Es aceptable y está acotado: las `TABLE<n>` son 722 tablas y **14.661 filas
en total** —una veintena de filas cada una— y a partir de la segunda pregunta sale
de memoria. El árbol de navegación, que es una lectura mucho más grande, ya se
carga así.

## 8. El predicado se evalúa en Python, no en SQL

El filtro por `SSTATREGT` sería trivial en SQL (`row->>'SSTATREGT' = '1'`). El de
período no: las fechas viven adentro del `jsonb` como texto, sin formato
declarado, y castearlas en SQL convierte un valor con formato inesperado en un
error de toda la consulta.

Así que el SQL filtra por `(tenant, env, run_id, table_name)` con `LIMIT tope + 1`
—el `+1` es cómo se detecta que hubo más y se reporta `rows_capped`— y el
predicado se evalúa en Python, donde una fecha que no parsea se **cuenta**
(`date_unparsed`) en vez de tumbar la consulta. Un solo lugar donde se decide qué
entra y qué no, y todos los descartes salen contados del mismo sitio.

Efecto que hay que aceptar y declarar: el tope se aplica **antes** del filtro de
vigencia, así que una tabla grande podría traer el tope entero y quedarse con
pocas vigentes. Para el alcance de este change es teórico —las `TABLE<n>` promedian
una veintena de filas— y cuando pase, `rows_capped` lo dice.

## 9. `NG_IDENTI` en el árbol, no en `NavigationLocation`

`NavigationLocation` viaja adentro de la metadata de los chunks. Agregarle un
campo cambiaría la metadata de 56.537 filas ya cargadas y obligaría a otro
backfill, por un dato que el chunk no necesita: `NG_IDENTI` lo usa el camino de
respuesta, no el de troceado.

Así que la columna se carga en `NavigationTree` —la estructura en memoria— con su
accesor, y `NavigationLocation` queda igual. El loader del CSV no la trae y no se
la inventa: sin corrida activa no hay bloque, que es la regla de §10 de este
diseño.

## 10. Sin corrida activa no hay bloque

El fallback de `window_status` es la columna estampada, y tiene sentido porque la
columna existe. Acá no hay equivalente: el diccionario y las filas **solo** viven
en el mirror. Sin corrida activa el bloque no se renderiza y
`AnswerResponse.business_db` lo dice con su razón, exactamente como
`resolve_active_run` distingue «no hay corrida» de «no hay corrida porque tampoco
hay configuración».

Lo que no se hace: caer a la corrida más reciente. Es la misma prohibición de
`add-extraction-run-selection`, por la misma razón.

# business-db-context Specification

## Purpose

Qué le llega a una respuesta desde la base de VisualTIME, además del corpus
funcional. El corpus manda sobre la intención —para qué sirve una transacción,
qué valida— y la base manda sobre **qué existe hoy**
([visualtime-database-metadata.md §10](../../domain/visualtime-database-metadata.md));
esta capability es la segunda autoridad, y cubre de punta a punta cómo se arma el
bloque: qué códigos anclan, qué tablas toca cada transacción —la que mantiene,
por `NG_IDENTI`, y las que sus rutinas leen o escriben, por el grafo de
dependencias de Oracle—, qué dice el diccionario de esas tablas, qué filas están
vigentes, y qué quedó afuera y por qué.

La incompletitud es parte del contrato y no una nota al pie: cada código anclado
termina en un resultado de un vocabulario **cerrado**, y el bloque cierra
diciendo qué no se pudo traer. Un bloque que calle lo que falta le hace afirmar
al modelo un catálogo entero que no vio.

Implementado en `app/generation/rag/business_db/` — `resolve.py` (el ancla y la
resolución de tablas), `reader.py` (diccionario y filas desde el mirror),
`validity.py` (el predicado de vigencia por tabla), `roles.py` (el rol de cada
tabla y el orden por cobertura), `render.py` (el único renderer del bloque y su
recorte) y `models.py` (el vocabulario de resultados).

Promovido de: `add-business-db-context`, `add-dependency-table-anchoring`,
`add-table-dictionary-panel`.

## Requirements

### Requirement: El contexto de base DEBE salir de la corrida activa, y sin corrida no DEBE haber bloque
Lo que el servicio trae del mirror para una respuesta sale de la corrida vigente
que resuelve `resolve_active_run` — la misma que resuelve el estado de ventana —
y de ninguna otra. Las tablas del mirror hacen upsert y nunca delete, así que
`run_id` significa *la última corrida que escribió esa fila*: leer sin filtrar por
corrida es responder sobre objetos que ya no existen.

Sin corrida vigente **no se renderiza ningún bloque**. No hay caída a la corrida
más reciente ni a otra fuente: el diccionario y las filas solo viven en el mirror,
y una respuesta que no dijera de dónde salió su catálogo no se puede verificar.

#### Scenario: El bloque nombra su corrida
- **WHEN** se arma el bloque con una corrida vigente
- **THEN** el texto nombra el `run_id` y el ambiente del que salió

#### Scenario: Toda consulta filtra por la corrida
- **WHEN** se leen `business_tables` o `business_data`
- **THEN** la consulta filtra por `(tenant, env, run_id)` de la corrida vigente

#### Scenario: Sin corrida vigente
- **WHEN** no hay corrida vigente al responder
- **THEN** no se renderiza bloque de base
- **AND** la respuesta declara que no lo hay y por qué
- **AND** no se usa la corrida más reciente

### Requirement: El ancla DEBEN ser los códigos de los hits que entraron al prompt
Los códigos que se resuelven contra el mirror son los `document_id` de los hits
que quedaron dentro del presupuesto de contexto, deduplicados y acotados por
configuración. Un hit que no llegó al prompt no ancla nada: el bloque describe lo
que la respuesta puede citar, no lo que la recuperación encontró.

El ancla es un dato declarado —`document_id` es el código de transacción y
`WINDOWS.SCODISPL` es la misma columna—, no una inferencia sobre el texto de la
pregunta.

#### Scenario: Solo los hits que entraron
- **WHEN** el presupuesto deja hits afuera
- **THEN** los códigos descartados no se resuelven contra el mirror

#### Scenario: Un código repetido se resuelve una vez
- **WHEN** dos hits comparten `document_id`
- **THEN** el bloque lleva una sola resolución para ese código

#### Scenario: Un código que la corrida no tiene
- **WHEN** un `document_id` no aparece en `WINDOWS` de la corrida vigente
- **THEN** se registra como `not_in_run`
- **AND** no se inventa ninguna tabla para él

### Requirement: La tabla que mantiene una transacción DEBE resolverse solo para el tipo de ventana 10
`WINDOWS.NG_IDENTI` declara la tabla genérica que mantiene la transacción, y esa
declaración solo significa algo para las ventanas de tipo 10 (Tabla general): de
529 pares de tipo 10 que resuelven a una tabla existente coinciden 440, y de los
11 pares de otros tipos coinciden 0.

Un `NG_IDENTI` distinto de cero en cualquier otro tipo se **ignora y se cuenta**.
Usarlo sería afirmar que un reporte mantiene una tabla de catálogo.

#### Scenario: Tipo 10 con tabla declarada
- **WHEN** el código es de tipo de ventana 10 y declara `NG_IDENTI` distinto de cero
- **THEN** se resuelve la `TABLE<n>` correspondiente

#### Scenario: Otro tipo con NG_IDENTI
- **WHEN** el código no es de tipo 10 y declara `NG_IDENTI` distinto de cero
- **THEN** no se resuelve ninguna tabla
- **AND** se registra como `ng_identi_ignored_by_type`

#### Scenario: La tabla declarada no existe en el diccionario
- **WHEN** la `TABLE<n>` resuelta no tiene fila en `business_tables` para la corrida
- **THEN** se registra como `table_not_in_dictionary`
- **AND** no se emite diccionario ni filas para ese código

### Requirement: El mecanismo de vigencia DEBE leerse de las columnas declaradas de cada tabla
Qué predicado de vigencia aplica a una tabla se deriva de las columnas que
`business_tables` declara para ella, no de una lista en código: la distribución
medida es de una corrida, y el extractor tiene su propio ciclo de release.

Los casos son cuatro y ninguno se resuelve a medias:

- solo `SSTATREGT` → `SSTATREGT = '1'`, normalizando el valor `4` a `3` y contándolo.
- período completo (`DEFFECDATE` y `DNULLDATE`) → `DEFFECDATE <= as_of AND (DNULLDATE > as_of OR DNULLDATE IS NULL)`.
- los dos mecanismos → los dos, midiendo y reportando las filas donde discrepan.
- media pareja, o ninguna columna → **sin mecanismo declarado**: no se filtra, y se dice.

La presencia de la columna no implica el mecanismo: hay tablas transaccionales
donde `DNULLDATE` es una fecha de anulación y el predicado ni siquiera cierra.

#### Scenario: Solo estado
- **WHEN** la tabla declara `SSTATREGT` y ninguna columna de período
- **THEN** se conservan las filas con `SSTATREGT = '1'`
- **AND** un valor `4` se lee como `3` y se cuenta aparte

#### Scenario: Solo período
- **WHEN** la tabla declara `DEFFECDATE` y `DNULLDATE`
- **THEN** se conservan las filas vigentes a la fecha de referencia

#### Scenario: Los dos mecanismos
- **WHEN** la tabla declara estado y período completo
- **THEN** se aplican los dos
- **AND** se reporta cuántas filas discrepan entre los dos criterios

#### Scenario: Media pareja
- **WHEN** la tabla declara `DEFFECDATE` sin `DNULLDATE`, o al revés
- **THEN** las filas no se filtran por vigencia
- **AND** se registra como `no_validity_mechanism`

#### Scenario: Columnas sin extraer
- **WHEN** `columns` es `NULL` para esa tabla
- **THEN** se registra como `columns_unknown`
- **AND** no se confunde con una tabla que declara `[]` columnas

### Requirement: La fecha de referencia DEBE ser la de la corrida y nunca el reloj de pared
El predicado de período necesita una fecha, y esa fecha es el `created_at_utc` de
la corrida vigente, sobreescribible por configuración. Nunca `now()`: un snapshot
de hace tres meses evaluado contra hoy afirma una vigencia que el dato no
respalda, y una respuesta que depende del reloj de pared pasa un eval hoy y lo
falla la semana que viene sin que nadie haya tocado nada.

#### Scenario: Default de la corrida
- **WHEN** no se configura una fecha de referencia
- **THEN** se usa el `created_at_utc` de la corrida vigente

#### Scenario: Fecha explícita
- **WHEN** se configura una fecha de referencia
- **THEN** la vigencia se evalúa contra esa fecha

#### Scenario: Una fecha que no parsea
- **WHEN** una fila trae un valor de fecha que no se puede interpretar
- **THEN** esa fila queda afuera con motivo `date_unparsed`
- **AND** la lectura de la tabla no falla

### Requirement: El bloque DEBE declarar que es otra autoridad
El corpus manda sobre la intención funcional y la base manda sobre qué existe hoy.
Cuando difieren no hay un error a resolver, hay un hallazgo a reportar. El bloque
lleva esa distinción adentro —no al lado—, va separado de los bloques de
evidencia, y dice que ante una diferencia con la especificación funcional hay que
señalarla en lugar de elegir una de las dos.

#### Scenario: El bloque se rotula
- **WHEN** se renderiza el bloque de base
- **THEN** el texto declara que no es documentación funcional
- **AND** instruye reportar la diferencia en vez de elegir una fuente

#### Scenario: No se mezcla con la evidencia
- **WHEN** se arma el prompt con evidencia y bloque de base
- **THEN** el bloque de base queda fuera de los bloques numerados de evidencia

### Requirement: El bloque DEBE declarar qué no se pudo traer, con su causa
Traer parte de un catálogo y presentarlo como entero es borrar información de
negocio en silencio. El bloque cierra con qué quedó afuera y por qué, y la
respuesta lleva la misma contabilidad estructurada.

Las causas son un vocabulario cerrado, sin categoría de descarte. Una causa nueva
se agrega al vocabulario; no existe «otro».

Se distingue **no había nada que traer** de **había algo y no llegó**. Que una
transacción no declare tabla que mantenga no es incompletitud: la base declaró que
no hay. Que la tabla no esté cargada, que se haya pasado del tope de filas o que
la haya recortado el presupuesto, sí.

#### Scenario: Se trajo todo lo que había
- **WHEN** ninguna resolución quedó incompleta
- **THEN** la respuesta declara el contexto completo
- **AND** una transacción que no declara tabla no lo vuelve incompleto

#### Scenario: Una tabla sin cargar
- **WHEN** la tabla resuelta no tiene filas en `business_data` para la corrida
- **THEN** se registra como `table_not_loaded`
- **AND** la respuesta declara el contexto incompleto
- **AND** el bloque nombra esa tabla en la sección de lo que no se pudo traer

#### Scenario: Una lista de filas recortada
- **WHEN** la tabla tiene más filas que el tope configurado
- **THEN** se registra como `rows_capped`
- **AND** la lista emitida lleva su conteo real, no el de lo mostrado

#### Scenario: Cada causa se nombra
- **WHEN** una resolución queda incompleta
- **THEN** la contabilidad lleva la causa de un vocabulario cerrado
- **AND** no existe una causa genérica de descarte

### Requirement: Un recorte declarado NO DEBE contar como incompletitud
`dependency_tables_capped` no es una ausencia muda: la sección dice con todas
las letras *«Tablas que toca: 17, se muestran 12»* y las doce son las de mayor
cobertura. El conteo es exacto y el orden es conocido, así que un lector sabe
cuánto le falta y de qué clase.

Eso lo separa de `edges_not_built` y de `table_not_loaded`, donde no se puede
saber qué se perdió. Medido sobre la corrida activa, el tope de 12 recorta el
**26% de los 460 códigos que tienen tablas**, y un turno ancla unos diez: contarlo
como incompletitud encendía el aviso en casi toda respuesta. Un aviso que salta
siempre enseña a ignorarlo, y entonces `edges_not_built` pasa desapercibido el
día que importa.

La causa SHALL seguir viajando en `causes` y SHALL seguir nombrándose en la
sección de cierre. Lo que NO SHALL hacer es volver incompleto el contexto.

#### Scenario: Solo un recorte declarado
- **WHEN** la única causa fuera de lo esperado es `dependency_tables_capped`
- **THEN** el contexto se declara completo

#### Scenario: El recorte igual se nombra
- **WHEN** una lista de tablas se recortó
- **THEN** la sección de cierre la nombra con su causa

#### Scenario: Una ausencia muda sí lo vuelve incompleto
- **WHEN** la causa es `edges_not_built` o `table_not_loaded`
- **THEN** el contexto se declara incompleto

#### Scenario: Una fila no se parte
- **WHEN** la siguiente fila no entra completa en lo que queda
- **THEN** esa fila se descarta entera
- **AND** se registra como `dropped_by_budget`
### Requirement: El bloque DEBE tener techo en tokens y recortarse en un orden declarado
El bloque se cobra **adentro** del techo de contexto de la respuesta y nunca
encima, y se ajusta después de la evidencia y después de la memoria: un chunk
desplazado cuesta una cita y un turno desplazado rompe una conversación, mientras
que el bloque de base es el único de los tres que puede declarar su propio
recorte.

El orden de recorte se declara y no se improvisa. Con la sección de tablas por
dependencia, el orden completo es: primero las tablas desde la cola del orden por
cobertura, después las filas de catálogo desde la cola, después las descripciones
de columna, después la descripción de la tabla.

Sin un rol `core` que proteger, **la cobertura es la protección**: se recorta la
tabla que menos rutinas de la transacción alcanzan. Hay un piso de una tabla por
código —un código sin ninguna se leería como *"no toca tablas"*, que es un hecho
distinto con su propia causa—, la declaración de la ventana no se recorta, una
fila nunca se parte al medio, y una tabla emitida nunca pierde las rutinas que la
justifican: si el techo no alcanza para eso, se recorta el código entero.

#### Scenario: La base no le saca presupuesto a la evidencia
- **WHEN** la evidencia consume todo el presupuesto
- **THEN** ningún chunk se descarta para dejar entrar el bloque de base

#### Scenario: La base no le saca presupuesto a la memoria
- **WHEN** la memoria ya tomó lo que quedaba
- **THEN** ningún turno se descarta para dejar entrar el bloque de base

#### Scenario: Recorte en el orden declarado
- **WHEN** el bloque no entra en su techo
- **THEN** se recortan primero las tablas desde la cola del orden por cobertura
- **AND** después las filas de catálogo
- **AND** la declaración de la ventana se conserva

#### Scenario: La mejor cubierta sobrevive
- **WHEN** el recorte de tablas llega al final
- **THEN** queda al menos una tabla por código
- **AND** es la de mayor cobertura

#### Scenario: Una lista de tablas recortada se cuenta
- **WHEN** la sección de tablas se recorta por presupuesto
- **THEN** se registra como `dependency_tables_capped`
- **AND** la sección lleva el conteo real, no el de lo mostrado
- **AND** eso NO vuelve incompleto el contexto

### Requirement: Las tablas que toca una transacción DEBEN salir del grafo de dependencias declarado
`WINDOWS.NG_IDENTI` solo declara la tabla que mantiene una ventana de tipo 10, y
para las transacciones de negocio no declara nada: medido sobre la corrida activa,
`CA014`, `CA025` y `CA048` traen `0` y `CA001` trae `NULL`. Para esos códigos el
bloque hoy no aporta una sola tabla.

Las tablas SHALL salir de `visualtime.business_dependencies` —las dependencias que
Oracle compiló entre sus objetos, 49.271 aristas hacia tablas en la corrida
activa— encadenando dos saltos: del `document_id` a las rutinas que lo nombran, y
de esas rutinas a sus tablas.

El segundo salto **no usa nombres**: es la dependencia declarada. Por eso `CA014`
llega a `COVER` sin que los nombres se parezcan.

Las dos vías conviven y no se colapsan: `NG_IDENTI` sigue siendo el camino del
tipo 10, y una arista de dependencia nunca se presenta como la tabla que la
transacción mantiene.

#### Scenario: Una transacción de negocio llega a sus tablas
- **WHEN** se ancla `CA014` contra la corrida activa
- **THEN** el bloque trae las tablas alcanzadas por sus rutinas
- **AND** `COVER` está entre ellas

#### Scenario: El tipo 10 conserva su camino
- **WHEN** se ancla un código de tipo de ventana 10 con `NG_IDENTI` distinto de cero
- **THEN** la tabla que mantiene se sigue resolviendo por `NG_IDENTI`
- **AND** las tablas por dependencia, si las hay, se emiten aparte

#### Scenario: Un código sin rutina propia
- **WHEN** ningún objeto Oracle de la corrida nombra al código
- **THEN** se registra como `no_dependency_routine`
- **AND** no se le atribuye ninguna tabla

#### Scenario: Una rutina que no depende de tablas
- **WHEN** el código resuelve rutinas y ninguna depende de una tabla
- **THEN** se registra como `routine_without_tables`
- **AND** eso no vuelve incompleto el contexto

### Requirement: El salto por nombre DEBE resolverse por el código más largo que matchea
El `document_id` contenido en el nombre del objeto Oracle es el único salto que
usa nombres, y los nombres se solapan: 184 códigos de largo ≥ 5 son substring de
otro código. `CA013` está adentro de `CA013A`, `AG001` adentro de `AG001_K` y de
`MAG001`. Sin desambiguar, `INSPOSTCA013A` le cuelga sus tablas a `CA013` — 55
pares así, sobre 31 documentos.

Para cada nombre de rutina SHALL ganar el código matcheante más largo, y solo ese
SHALL llevarse la arista. No es un desempate estadístico: `INSPOSTCA013A` nombra a
`CA013A` de manera inequívoca.

Un código de largo menor a 5 SHALL NOT anclar. Los de largo 4 producen falsos
positivos puros —`LOGO → INSCOPYCATALOGO`, `MENU → REAWINDOWSMENUPKG`— y se
cuentan en vez de descartarse en silencio.

#### Scenario: La variante se queda con su rutina
- **WHEN** existen `CA013` y `CA013A`, y una rutina se llama `INSPOSTCA013A`
- **THEN** esa rutina ancla a `CA013A`
- **AND** NO ancla a `CA013`

#### Scenario: El código corto conserva lo suyo
- **WHEN** una rutina se llama `INSPOSTCA013`
- **THEN** ancla a `CA013`

#### Scenario: Un código corto que queda sin rutinas
- **WHEN** todas las rutinas que matcheaban a un código se las llevó un código más largo
- **THEN** ese código se registra como `no_dependency_routine`
- **AND** no hereda ninguna tabla del código largo

#### Scenario: Código de largo 4
- **WHEN** se ancla un código de cuatro caracteres
- **THEN** no se resuelve ninguna rutina
- **AND** se registra como `code_too_short_to_anchor`

### Requirement: Cada tabla DEBE llevar su rol, de un vocabulario cerrado y derivado de reglas ordenadas
El rol SHALL salir de reglas ordenadas expresadas como datos `(patrón, rol)` —el
mismo patrón que la taxonomía de códigos—, auditables y editables cuando aparezca
un contraejemplo, nunca de una llamada a un modelo ni del texto del chunk.

El vocabulario es cerrado: `reference`, `historical`, `message`, `validation`,
`unknown`. Las señales del destino —lo que `business_tables` dice de la tabla—
SHALL ganarle a las del camino, porque describen qué es la tabla y no cómo se
llegó a ella.

**No hay rol `core`, y su ausencia es un resultado de medición.** Contra las
cuatro transacciones anotadas, la regla que lo derivaría de un fan-in bajo corre
al revés: las tablas que el analista nombra son las de fan-in más alto del
sistema —`CERTIFICAT` 1.989, `CLIENT` 1.925, `COVER` 1.037— y las de fan-in bajo
—`NOPAYROLL` 44, `CUR_ALLOW` 30— no lo son. Una entidad central la toca todo
**porque** es central. Ninguna otra señal declarada la aísla, así que el servicio
SHALL NOT afirmar `core`.

#### Scenario: Catálogo de contenido fijo
- **WHEN** la tabla se llama `TABLE<n>` o su descripción declara contenido fijo
- **THEN** el rol es `reference`

#### Scenario: Tabla de historia
- **WHEN** la tabla tiene sufijo `_HIS` o su descripción de negocio empieza por Historia
- **THEN** el rol es `historical`

#### Scenario: Tabla de mensajes
- **WHEN** la tabla es `MESSAGE` o `WIN_MESSAG`
- **THEN** el rol es `message`

#### Scenario: Alcanzada solo por validación
- **WHEN** todas las rutinas que alcanzan la tabla llevan prefijo de validación
- **THEN** el rol es `validation`

#### Scenario: Alcanzada también por otra clase de rutina
- **WHEN** la alcanzan rutinas de validación y también de escritura o de lectura
- **THEN** el rol NO es `validation`

#### Scenario: Ninguna regla aplica
- **WHEN** la tabla no matchea ninguna regla
- **THEN** el rol es `unknown`
- **AND** se registra la razón, nombrando las clases de rutina vistas
- **AND** se registra la causa `role_unknown`

#### Scenario: El orden separa lo específico de lo genérico
- **WHEN** una tabla matchea una señal del destino y también una del camino
- **THEN** gana la del destino, porque las reglas se recorren en orden

#### Scenario: El vocabulario no tiene core
- **WHEN** se consulta el vocabulario de roles
- **THEN** `core` no está en él

### Requirement: Las tablas SE DEBEN ordenar por cobertura, y el orden NO DEBE leerse como jerarquía
Un código llega a 8 tablas en la mediana y hasta 185. Emitirlas sin orden cambia
un bloque mudo por uno que dice demasiado.

El orden SHALL ser la **cobertura**: cuántas rutinas de la transacción alcanzan la
tabla, sobre cuántas tiene. Son dos conteos declarados divididos, sin umbral que
elegir — la misma razón por la que la fusión del retrieval usa posiciones y no
puntajes calibrados. Los dos conteos SHALL viajar con la tabla.

El bloque SHALL decir que ese orden no es una jerarquía de importancia declarada,
para que el modelo no lea el primer puesto como una afirmación de la base.

#### Scenario: Mayor cobertura primero
- **WHEN** una tabla la alcanzan 3 de 3 rutinas y otra 1 de 3
- **THEN** la primera va antes

#### Scenario: Los conteos viajan
- **WHEN** se emite una tabla
- **THEN** lleva cuántas rutinas la alcanzan y cuántas tiene la transacción

#### Scenario: El bloque desarma la lectura de jerarquía
- **WHEN** se renderiza la sección de tablas
- **THEN** el texto dice que el orden es por cobertura y no una jerarquía declarada

### Requirement: El fan-in SE DEBE guardar y NO SE DEBE usar para degradar una tabla
Cada arista SHALL guardar cuántas rutinas de toda la corrida dependen de esa
tabla, para que la decisión de rol se pueda revisar cuando el set anotado crezca
sin reconstruir las aristas.

Ese número SHALL NOT degradar ni descartar una tabla. Medido, corre al revés de
lo que la intuición sugiere: las tablas que el analista nombra son las de fan-in
más alto. Un fan-in alto dice que la tabla es transversal, y no que sea menos
importante.

#### Scenario: El fan-in viaja con la arista
- **WHEN** se emite una tabla por dependencia
- **THEN** lleva su fan-in

#### Scenario: Una tabla ubicua no se degrada
- **WHEN** una tabla tiene el fan-in más alto de la lista
- **THEN** igual se emite
- **AND** su posición la decide la cobertura, no el fan-in

### Requirement: Cada tabla emitida DEBE nombrar las rutinas que la justifican
Una tabla afirmada sin decir por qué entró no se puede verificar, y es el mismo
defecto que un chunk sin procedencia. El bloque SHALL nombrar, para cada tabla,
las rutinas de las que salió la dependencia, y la respuesta SHALL llevar esa misma
lista estructurada.

Esa lista SHALL NOT recortarse por presupuesto: sin ella la tabla deja de ser
citable y pasa a ser una afirmación sin origen.

#### Scenario: Procedencia de la tabla
- **WHEN** el bloque emite `COVER` para `CA014`
- **THEN** nombra las rutinas por las que se alcanzó

#### Scenario: La procedencia sobrevive al recorte
- **WHEN** el bloque se recorta por presupuesto
- **THEN** ninguna tabla emitida queda sin su lista de rutinas

### Requirement: Una corrida sin aristas construidas DEBE declararse, no quedar muda
Las aristas se materializan en un batch por corrida. Activar una corrida para la
que ese batch nunca corrió deja el bloque sin tablas, y un bloque vacío es
indistinguible de una transacción que no toca ninguna.

Cuando la corrida activa no tiene aristas construidas, la resolución SHALL
registrar `edges_not_built` y el contexto SHALL declararse incompleto: había algo
y no llegó.

#### Scenario: Corrida sin batch
- **WHEN** la corrida activa no tiene aristas materializadas
- **THEN** cada código anclado se registra como `edges_not_built`
- **AND** la respuesta declara el contexto incompleto
- **AND** el bloque nombra la causa

#### Scenario: No se cae a las aristas de otra corrida
- **WHEN** hay aristas de una corrida anterior y ninguna de la activa
- **THEN** no se usan las anteriores

<!-- Promovido de: add-dependency-table-anchoring -->
### Requirement: Cada tabla emitida DEBE decir qué es
Un nombre de tabla solo no informa. `CESSION_NPR` y `CESSION_PR` son la
diferencia entre reaseguro no proporcional y proporcional, y el modelo no tiene
cómo saberlo salvo que la prosa de negocio viaje con el nombre.

Cada tabla emitida SHALL llevar la descripción que `business_tables` declara para
ella en la corrida vigente. La lectura SHALL resolverse en la misma consulta que
trae las aristas, no una por tabla.

Una tabla sin ficha en el diccionario SHALL emitirse igual: la dependencia está
declarada de todos modos, y callarla por no tener descripción perdería un hecho.

#### Scenario: La descripción viaja con la tabla
- **WHEN** se emite `CESSION_NPR` para `CRL050`
- **THEN** el bloque lleva su descripción de negocio

#### Scenario: Una tabla sin ficha igual se emite
- **WHEN** la tabla no tiene fila en `business_tables` para la corrida
- **THEN** se emite igual, sin descripción

#### Scenario: Una sola consulta
- **WHEN** se leen las tablas de un código
- **THEN** las descripciones vienen en esa misma lectura

### Requirement: El diccionario completo de una tabla SE DEBE poder leer aparte
El diccionario entero —las columnas con su descripción y su tipo, la clave
primaria, las foráneas con su tabla destino, los índices— es lo que hace falta
para entender una tabla, y no cabe en el prompt: medido, 12 tablas en ese formato
son 15.969 tokens contra un techo de contexto de 16.384 que ya usa 7.000 en
evidencia.

El servicio SHALL exponer ese diccionario por tabla en un endpoint propio, de la
corrida vigente, para que se lea cuando alguien lo pide y no en cada turno.

#### Scenario: El diccionario de una tabla
- **WHEN** se pide el diccionario de `CESSION_NPR`
- **THEN** se devuelven su descripción, sus columnas con descripción y tipo, su
  clave primaria, sus foráneas con la tabla destino, y sus índices

#### Scenario: Una tabla que la corrida no tiene
- **WHEN** se pide una tabla que no está en `business_tables` de la corrida
- **THEN** responde 404

#### Scenario: Sin corrida vigente
- **WHEN** no hay corrida vigente
- **THEN** responde 409
- **AND** no se cae a la corrida más reciente

#### Scenario: Columnas sin extraer no se confunden con una tabla sin columnas
- **WHEN** `columns` es `NULL` para esa tabla
- **THEN** la respuesta lo declara como no extraídas
- **AND** NO como una lista vacía

<!-- Promovido de: add-table-dictionary-panel -->

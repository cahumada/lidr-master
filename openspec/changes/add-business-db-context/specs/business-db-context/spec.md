# business-db-context Delta Specification

## ADDED Requirements

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

### Requirement: El bloque DEBE tener techo en tokens y recortarse en un orden declarado
El bloque se cobra **adentro** del techo de contexto de la respuesta y nunca
encima, y se ajusta después de la evidencia y después de la memoria: un chunk
desplazado cuesta una cita y un turno desplazado rompe una conversación, mientras
que el bloque de base es el único de los tres que puede declarar su propio
recorte.

El orden de recorte se declara y no se improvisa: primero las filas desde la cola,
después las descripciones de columna, después la descripción de la tabla. La
declaración de la ventana no se recorta. Una fila nunca se parte al medio.

#### Scenario: La base no le saca presupuesto a la evidencia
- **WHEN** la evidencia consume todo el presupuesto
- **THEN** ningún chunk se descarta para dejar entrar el bloque de base

#### Scenario: La base no le saca presupuesto a la memoria
- **WHEN** la memoria ya tomó lo que quedaba
- **THEN** ningún turno se descarta para dejar entrar el bloque de base

#### Scenario: Recorte en el orden declarado
- **WHEN** el bloque no entra en su techo
- **THEN** se recortan primero las filas desde la cola
- **AND** la declaración de la ventana se conserva

#### Scenario: Una fila no se parte
- **WHEN** la siguiente fila no entra completa en lo que queda
- **THEN** esa fila se descarta entera
- **AND** se registra como `dropped_by_budget`

# business-db-context Delta Specification

## ADDED Requirements

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

## MODIFIED Requirements

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

#### Scenario: Una fila no se parte
- **WHEN** la siguiente fila no entra completa en lo que queda
- **THEN** esa fila se descarta entera
- **AND** se registra como `dropped_by_budget`

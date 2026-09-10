# extraction-run-selection Delta Specification

## ADDED Requirements

### Requirement: La corrida del mirror SE DEBE elegir, nunca descubrir
El mirror acumula corridas del extractor —tres al momento de escribir esto, en
dos ambientes y con distinto grado de carga— y el servicio lee de **una**. Cuál
es se elige explícitamente y queda registrado, por la misma razón por la que
activar una versión del corpus es explícito: una corrida a medias no debe poder
activarse sola, y "la más reciente" haría que lo que el servicio responde cambie
sin que nadie lo haya decidido.

La selección vive en el esquema del servicio, no en `visualtime.*`: esas tablas
las escribe otro repo y acá se leen. Y a lo sumo una corrida está activa por
cliente, garantizado por la base y no por código de aplicación.

#### Scenario: Una sola corrida activa por cliente
- **WHEN** se activa una corrida para un cliente que ya tenía otra activa
- **THEN** la anterior deja de estar activa
- **AND** la base impide que queden dos activas a la vez

#### Scenario: Sin selección ni valor por defecto
- **WHEN** no hay corrida activa ni valor en la configuración
- **THEN** el servicio informa que no hay corrida vigente y su razón
- **AND** NO elige la más reciente por su cuenta

#### Scenario: Nada se escribe en el mirror
- **WHEN** se activa una corrida
- **THEN** solo se escribe en las tablas del esquema del servicio
- **AND** `visualtime.extraction_runs` queda intacta

### Requirement: Una corrida sin datos cargados NO DEBE poder activarse
El árbol de navegación se arma del contenido de `WINDOWS`, que vive en
`business_data`. Activar una corrida con `loaded_data = false` dejaría todos los
códigos sin resolver: breadcrumbs vacíos, sin tipo de ventana y sin estado, con
el servicio funcionando y respondiendo peor sin decir por qué.

Las tres banderas de carga son independientes, así que se exige la que la
funcionalidad necesita y se informan las otras dos para que quien elige sepa qué
cubre cada corrida.

#### Scenario: Corrida sin contenido
- **WHEN** se intenta activar una corrida cuyo `loaded_data` es falso
- **THEN** la activación se rechaza con un error que nombra la bandera faltante
- **AND** la selección anterior no cambia

#### Scenario: El listado declara qué cubre cada corrida
- **WHEN** se listan las corridas disponibles
- **THEN** cada una informa sus tres banderas de carga, su `created_at_utc`, su
  `extractor_version` y el hash de su manifest

### Requirement: La configuración DEBE ser el valor por defecto, no un override
`BUSINESS_DB_RUN_ID` es la corrida con la que el servicio arranca cuando **nadie
eligió todavía** — una instalación nueva funciona sin que un administrador entre
a la consola. En cuanto hay una selección, esa selección gana: quien opera el
producto está por encima de quien lo despliega, para esta decisión.

Es el mecanismo de **semilla** que `providers_store` ya usa —*"las tablas se
siembran del registro de código y de `ANSWER_MODEL_CATALOG` en el primer
arranque"*— y no el de **override**, que en ese mismo módulo se reserva para las
credenciales. La diferencia es deliberada: una clave en el ambiente es una
decisión de gestión de secretos del despliegue, y con qué corrida del mirror se
trabaja es una decisión de operación del producto.

La semilla NO se materializa como fila: una fila haría parecer que alguien
eligió esa corrida, y nadie lo hizo. Se resuelve al leer, y el origen de la
corrida vigente se informa —seleccionada o por defecto— para que se pueda
distinguir.

#### Scenario: Sin selección, manda la configuración
- **WHEN** no hay ninguna corrida activa y la configuración declara una
- **THEN** el servicio trabaja con esa corrida
- **AND** informa que su origen es la configuración y no una selección

#### Scenario: Con selección, manda la selección
- **WHEN** hay una corrida activa y la configuración declara otra
- **THEN** el servicio trabaja con la activa
- **AND** la activación NO se rechaza por existir un valor en la configuración

#### Scenario: La semilla no se guarda como elección
- **WHEN** el servicio resuelve la corrida desde la configuración
- **THEN** no se escribe ninguna fila de selección

### Requirement: Se DEBE saber con qué corrida se estampó el corpus
La metadata estampada en los chunks sale de una corrida concreta. Si después se
activa otra, ese valor queda viejo — y un desfasaje invisible entre lo estampado
y lo activo es la clase de defecto que nadie descubre hasta que una respuesta ya
salió mal.

Por eso el estampado registra su corrida, y esa información se expone junto a la
corrida activa: el desfasaje se muestra, no se deduce.

#### Scenario: El backfill registra su corrida
- **WHEN** termina un estampado de metadata sobre el corpus
- **THEN** queda registrado con qué corrida se hizo, cuándo y cuántas filas tocó

#### Scenario: Estampado y activa no coinciden
- **WHEN** la corrida activa es distinta de la que estampó el corpus
- **THEN** las dos se informan
- **AND** no se corrige nada automáticamente

### Requirement: Quién activó DEBE viajar como dato declarado
El servicio no autentica: los roles viven en el token de sesión de la consola y
el gate de administrador se aplica ahí. Entonces el servicio no puede verificar
la identidad de quien activa.

Se guarda lo que quien llama informa, y se documenta como **declarado**. Un
registro que parece autoritativo sin serlo es peor que no tenerlo.

#### Scenario: Activación con autor informado
- **WHEN** se activa una corrida informando quién lo hace
- **THEN** ese valor queda guardado como declarado por quien llamó

#### Scenario: Activación sin autor
- **WHEN** no se informa
- **THEN** la activación procede y el campo queda ausente
- **AND** no se inventa un autor

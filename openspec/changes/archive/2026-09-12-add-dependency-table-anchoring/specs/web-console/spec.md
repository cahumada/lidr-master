# web-console Delta Specification

## ADDED Requirements

### Requirement: El turno de respuesta muestra de dónde salió el contexto de base
El servicio devuelve `business_db` en la respuesta desde `add-business-db-context`
y la consola hoy lo tira: `lib/ai-service/types.ts` no tiene el campo y ninguna
pantalla lo lee. El operador no puede saber si la respuesta se apoyó en la base,
de qué corrida, ni qué quedó afuera.

La pantalla de respuesta SHALL mostrar, para el turno que trae `business_db` con
bloque emitido, la corrida y el ambiente de los que salió, y por cada código
anclado la cadena **código → rutinas → tablas**, con el rol de cada tabla.

La cadena SHALL mostrarse colapsada por defecto: es procedencia, no la respuesta.
Un turno sin bloque de base SHALL NOT mostrar la sección, y SHALL NOT mostrarse
como si el bloque hubiera salido vacío.

#### Scenario: La cadena es visible
- **WHEN** un turno vuelve con `business_db` y bloque emitido
- **THEN** el turno ofrece ver la corrida, el ambiente y los códigos anclados
- **AND** cada tabla se ve con su rol y con las rutinas que la justifican

#### Scenario: Colapsada por defecto
- **WHEN** el turno se renderiza
- **THEN** la cadena no está desplegada
- **AND** desplegarla no vuelve a pedir la respuesta

#### Scenario: Turno sin bloque de base
- **WHEN** `business_db` viene ausente, o con el bloque sin emitir
- **THEN** el turno no muestra la sección

#### Scenario: Servicio anterior
- **WHEN** la respuesta no trae el campo
- **THEN** el turno se renderiza igual, sin la sección

### Requirement: Un contexto de base incompleto se muestra como incompleto, con su causa
Una respuesta apoyada en un catálogo recortado presentado como entero borra
información de negocio en silencio — es el mismo defecto que el servicio ya trata
con su vocabulario cerrado de causas, y arreglarlo solo del lado del servicio lo
deja a medio arreglar.

Cuando `business_db.complete` es false, la pantalla SHALL avisarlo con el mismo
peso visual que el aviso de evidencia recortada, y el aviso SHALL nombrar la causa
que vino del servicio. Un rol `unknown` SHALL verse como `unknown` y no como una
tabla sin rol.

La consola SHALL NOT traducir una causa que no conoce a un texto genérico: una
causa nueva se muestra con su nombre, porque el vocabulario es cerrado del lado
del servicio y una etiqueta desconocida es un despliegue desfasado, no un error
del usuario.

**`dropped_codes` también es una causa y también se nombra.** Es la única
incompletitud que no viaja como causa de una resolución —el tope descartó esos
códigos *antes* de resolver nada para ellos, así que no hay resolución que la
lleve—, y leyendo solo las causas el aviso caía a un texto genérico justo en el
caso más común. Un `complete: false` que el servicio no explique con ninguna de
las dos vías SHALL reportarse como defecto del servicio, no como un aviso vago.

#### Scenario: Contexto incompleto
- **WHEN** un turno vuelve con `complete` en false
- **THEN** se muestra un aviso de que el contexto de base quedó incompleto
- **AND** el aviso nombra las causas que trajo la respuesta

#### Scenario: Aristas sin construir
- **WHEN** la causa es `edges_not_built`
- **THEN** el aviso dice que la corrida activa no tiene las tablas por dependencia construidas
- **AND** enlaza a la pantalla de corridas

#### Scenario: Rol desconocido
- **WHEN** una tabla viene con rol `unknown`
- **THEN** se muestra como desconocido
- **AND** no se muestra con el rol de otra tabla ni sin rol

#### Scenario: Causa que la consola no conoce
- **WHEN** la respuesta trae una causa que el cliente no tiene mapeada
- **THEN** se muestra el nombre de la causa tal como vino

#### Scenario: Códigos que el tope dejó afuera
- **WHEN** el contexto viene incompleto solo porque `dropped_codes` no está vacío
- **THEN** el aviso nombra el tope de códigos anclados
- **AND** lista los códigos que quedaron afuera

#### Scenario: Incompletitud que nadie nombra
- **WHEN** `complete` es false y no hay ni causas ni `dropped_codes`
- **THEN** el aviso dice que el servicio no nombró la causa
- **AND** NO se muestra un texto genérico como si fuera una explicación

### Requirement: La pantalla de corridas dice si una corrida tiene sus aristas construidas
Las tablas por dependencia se materializan en un batch por corrida. Activar una
corrida para la que ese batch nunca corrió deja el bloque de base sin tablas, y
hoy nada lo anticipa: el administrador se entera cuando una respuesta sale pobre.

La pantalla de corridas SHALL mostrar, por cada corrida listada, si tiene aristas
construidas y de cuándo. Activar una corrida sin aristas SHALL pedir confirmación
que diga qué se degrada, y SHALL NOT bloquearse: puede ser deliberado mientras el
batch corre.

#### Scenario: Estado por corrida
- **WHEN** el administrador abre la pantalla de corridas
- **THEN** cada fila dice si tiene aristas construidas y cuándo

#### Scenario: Activar una corrida sin aristas
- **WHEN** el administrador activa una corrida sin aristas construidas
- **THEN** se le pide confirmación
- **AND** el texto dice que las respuestas no van a traer tablas por dependencia

#### Scenario: No se bloquea
- **WHEN** el administrador confirma
- **THEN** la corrida se activa

### Requirement: La pantalla de flujo declara el anclaje de base como paso de la resolución
`/agents/flow` existe para mostrar cómo resuelve el servicio, y arma sus nodos
desde `config.flow` sin declarar nada en TypeScript. A partir del anclaje por
dependencias la resolución tiene un paso que el diagrama no nombra: el contexto de
base que entra al sintetizador sin pasar por un agente.

La pantalla SHALL mostrar ese paso cuando el servicio lo declare en `GET /config`,
con lo que recibe (los códigos de los hits) y lo que deja (las tablas con su rol).
SHALL NOT dibujarlo desde una constante local: si el servicio no lo declara, la
pantalla no lo muestra.

#### Scenario: El paso sale del servicio
- **WHEN** `GET /config` declara el paso de anclaje de base
- **THEN** la pantalla lo muestra en el recorrido, con su par entra → sale

#### Scenario: Servicio que no lo declara
- **WHEN** `GET /config` no trae ese paso
- **THEN** la pantalla no lo dibuja
- **AND** el resto del flujo se muestra igual

#### Scenario: No es un nodo del grafo
- **WHEN** el usuario mira el diagrama de aristas
- **THEN** el paso de anclaje no aparece como un especialista con vuelta al orquestador

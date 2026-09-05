# web-console Delta Specification

## MODIFIED Requirements

### Requirement: Pantalla de flujo del grafo
La consola SHALL servir `/agents/flow` con un diagrama y las fichas de
los nodos armados desde `config.flow` (nodos, `kind`, aristas,
escalera, ejemplo). La pantalla SHALL presentar los nodos en orden de
ejecución —orquestador, después `flow.ladder`, después el gate— y SHALL
mostrar en cada ficha el par entra → sale del ejemplo servido, con la
pregunta de ejemplo visible una vez arriba. El ejemplo del agente
LLM-driven y los documentos recuperados SHALL estar marcados como
ilustrativos; el resto sale de nodos deterministas. La pantalla SHALL
NOT declarar el grafo en TypeScript ni editar aristas. Si el servicio no
responde, SHALL decirlo y no inventar nodos. La navegación de
Configuración SHALL incluir esta pantalla junto a Agentes.

#### Scenario: el flujo muestra los nodos del servicio
- **WHEN** el usuario abre Configuración → Flujo
- **THEN** ve cada nodo que `GET /config` declara, con su `kind`
- **AND** las aristas coinciden con `config.flow`, no con un array local

#### Scenario: el recorrido usa una pregunta real
- **WHEN** el usuario mira la pantalla
- **THEN** ve la pregunta de ejemplo del servicio con su procedencia
- **AND** cada nodo muestra qué recibe y qué deja para esa pregunta

#### Scenario: lo que no es determinista se marca
- **WHEN** el usuario mira la ficha del sintetizador
- **THEN** su ejemplo aparece señalado como ilustrativo, porque la
  salida depende del modelo y de la persona

#### Scenario: servicio caído
- **WHEN** `GET /config` falla
- **THEN** la pantalla informa que no pudo leer el flujo
- **AND** no dibuja nodos de respaldo escritos en el cliente

## ADDED Requirements

### Requirement: El diagrama se deriva de las aristas servidas
El diagrama SHALL derivar su forma de hub —nodo supervisor central,
especialistas que vuelven a él, terminal sin vuelta— de `flow.edges`.
Cuando las aristas servidas no tengan esa forma, la pantalla SHALL caer
a la lista plana de aristas en vez de dibujar una topología que el
servicio no declaró.

#### Scenario: el grafo de hoy se dibuja como hub
- **WHEN** `flow.edges` trae el orquestador con vuelta desde cada
  especialista
- **THEN** el diagrama muestra el hub, sus radios y el terminal

#### Scenario: otra topología cae a la lista
- **WHEN** las aristas servidas no permiten identificar un hub
- **THEN** la pantalla lista las aristas tal como vienen

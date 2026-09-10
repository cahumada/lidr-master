# web-console Delta Specification

## ADDED Requirements

### Requirement: Alta y edición de perfiles nombrados
La consola SHALL permitir crear, editar, marcar como default y borrar
perfiles nombrados del agente configurable, con nombre, persona y knobs
de modelo. La lista SHALL salir de `GET /config`, no de estado local.
Los agentes deterministas SHALL seguir siendo fichas de solo lectura
que muestran rol, explicación y herramientas del catálogo. La
consola SHALL NOT ofrecer asignar tools ni crear un nodo del grafo.

#### Scenario: crear un perfil nombrado
- **WHEN** el usuario guarda un perfil `Conservador` con una persona
- **THEN** la lista de `/agents` lo muestra
- **AND** `GET /config` lo reporta bajo `answer_synthesizer`

#### Scenario: elegir el default
- **WHEN** el usuario marca `Exhaustivo` como default
- **THEN** la pantalla lo distingue de los demás
- **AND** una corrida sin `profile_id` usa ese perfil

#### Scenario: los deterministas no tienen alta
- **WHEN** el usuario mira un agente determinista
- **THEN** ve rol, explicación y tools
- **AND** no ve un formulario de nombre ni de persona

### Requirement: Pantalla de flujo del grafo
La consola SHALL servir `/agents/flow` con un diagrama y una tabla
armados desde `config.flow` (nodos, `kind`, aristas, escalera). La
pantalla SHALL NOT declarar el grafo en TypeScript ni editar aristas.
Si el servicio no responde, SHALL decirlo y no inventar nodos. La
navegación de Configuración SHALL incluir esta pantalla junto a
Agentes.

#### Scenario: el flujo muestra los nodos del servicio
- **WHEN** el usuario abre Configuración → Flujo
- **THEN** ve cada nodo que `GET /config` declara, con su `kind`
- **AND** las aristas coinciden con `config.flow`, no con un array local

#### Scenario: servicio caído
- **WHEN** `GET /config` falla
- **THEN** la pantalla informa que no pudo leer el flujo
- **AND** no dibuja nodos de respaldo escritos en el cliente

### Requirement: Una corrida puede elegir el perfil
La pantalla de respuesta SHALL ofrecer un selector con los perfiles
nombrados del sintetizador. Vacío o «default» SHALL omitir
`profile_id` y usar el default del servicio. Elegir un perfil SHALL
mandar su id en esa corrida y no cambiar el default.

#### Scenario: preguntar con un perfil puntual
- **WHEN** el usuario elige `Conservador` y envía una pregunta
- **THEN** el request lleva ese `profile_id`
- **AND** el default persistido no cambia

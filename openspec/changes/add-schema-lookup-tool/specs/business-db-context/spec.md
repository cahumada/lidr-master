# business-db-context Delta Specification

## ADDED Requirements

### Requirement: Tabla a pedido del modelo

El contexto de base expone al sintetizador una herramienta `describe_table` que
devuelve la ficha de una tabla —columnas, descripciones y tablas relacionadas por
el grafo de dependencias— leída de la corrida activa. El modelo emite la
intención de llamarla; el servicio ejecuta la lectura y devuelve el resultado al
modelo, que puede encadenar otra llamada o responder. La vía existe para las
tablas que el anclaje textual por código no alcanza: **no reemplaza el bloque
empujado**, que sigue siendo el camino por defecto.

#### Scenario: La pregunta nombra una tabla que ningún hit ancla
- **WHEN** el turno pregunta por una tabla cuyo código de transacción no aparece
  textualmente en ningún hit, y el flag está encendido
- **THEN** el modelo puede pedir esa tabla por `describe_table`, el servicio
  devuelve su ficha de la corrida activa, y la respuesta puede citarla

#### Scenario: El nombre pedido no está declarado
- **WHEN** el modelo pide una tabla que la corrida activa no declara
- **THEN** la herramienta devuelve un resultado explícito de "no declarada" y el
  turno continúa, sin excepción que lo corte

#### Scenario: El flag está apagado
- **WHEN** el flag está apagado
- **THEN** no se expone ninguna herramienta al sintetizador y el contexto se arma
  exactamente como hoy, en una sola llamada determinista

### Requirement: El tope de llamadas es una ausencia declarada

El bucle tiene un tope de vueltas y un tope de tablas por turno. Agotarlo no
degrada la respuesta en silencio: se registra como causa de incompletitud con el
vocabulario cerrado que la capability ya usa.

#### Scenario: El modelo pide más tablas que el tope
- **WHEN** el modelo sigue emitiendo llamadas después del tope de vueltas
- **THEN** el contexto lleva la causa `tool_budget_exhausted` y el bloque declara
  que hubo tablas pedidas que no se trajeron

### Requirement: La traza de llamadas es visible

Cada llamada del turno —tabla pedida, vuelta y resultado— viaja en el contexto de
base para que la consola pueda mostrarla. Un administrador tiene que poder leer
qué se le terminó diciendo al modelo, no solo lo que se le empujó al empezar.

#### Scenario: Un administrador inspecciona un turno que usó la herramienta
- **WHEN** un administrador abre la inspección de un turno donde el modelo pidió
  tablas
- **THEN** ve cada tabla pedida, en qué vuelta y con qué resultado, además del
  bloque que se empujó al principio

# business-db-context Delta Specification

## ADDED Requirements

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

# web-console Delta Specification

## ADDED Requirements

### Requirement: El diccionario de una tabla se abre desde el contexto de base
El panel de contexto de base nombra las tablas que toca cada transacción y, con
este change, qué es cada una. Lo que no cabe en el prompt —las columnas, sus
descripciones, la clave primaria, las foráneas y los índices— es justamente lo
que hace falta para entender una tabla.

El nombre de cada tabla del panel SHALL abrir su diccionario. El contenido SHALL
pedirse al abrir y no antes: una tabla puede tener 132 columnas y en un turno hay
hasta doce tablas por código.

La ficha SHALL estar disponible para cualquier sesión, sin exigir
`administrador`: el bloque de base ya se muestra en el turno a quien sea, y la
ficha es más de la misma autoridad. El prompt completo sigue siendo lo único
restringido, porque lleva la persona y los guardrails.

#### Scenario: Abrir el diccionario
- **WHEN** el usuario abre una tabla del panel de contexto de base
- **THEN** ve sus columnas con descripción y tipo, su clave primaria, sus
  foráneas con la tabla destino, y sus índices

#### Scenario: Se pide al abrir
- **WHEN** el panel se renderiza y ninguna tabla está abierta
- **THEN** no se pidió ningún diccionario

#### Scenario: Una tabla sin ficha
- **WHEN** el servicio responde 404 porque la corrida no tiene esa tabla
- **THEN** la ficha lo dice
- **AND** no se muestra vacía como si la tabla no tuviera columnas

#### Scenario: Una tabla ancha sigue siendo legible
- **WHEN** la tabla tiene más columnas de las que entran en pantalla
- **THEN** la lista scrollea en su propio contenedor
- **AND** se puede filtrar por nombre de columna

#### Scenario: Columnas no extraídas
- **WHEN** la corrida no extrajo las columnas de esa tabla
- **THEN** la ficha lo dice explícitamente
- **AND** no se muestra como una tabla sin columnas

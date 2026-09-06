# web-console Delta Specification

## ADDED Requirements

### Requirement: Una respuesta incompleta se muestra como incompleta

La pantalla de respuesta SHALL avisar cuando `answer_truncated` es true, con
el mismo peso visual que el aviso de evidencia recortada. Media respuesta
presentada como una respuesta entera es el defecto que este change cierra, y
arreglarlo solo en el servicio lo dejaría a medio arreglar.

El aviso SHALL decir DONDE se corrige --el tope de salida del perfil vigente,
editable en `/agents`-- y no solo que la respuesta se cortó. Un aviso que
nombra el problema sin nombrar la palanca deja al usuario adivinando.

#### Scenario: respuesta cortada por el tope de salida

- **WHEN** un turno vuelve con `answer_truncated` en true
- **THEN** el turno muestra un aviso de que la respuesta quedó incompleta
- **AND** el aviso nombra el tope de salida del perfil como lo que hay que
  subir

#### Scenario: respuesta completa

- **WHEN** un turno vuelve con `answer_truncated` en false
- **THEN** no se muestra ningún aviso de truncado

#### Scenario: turno pausado en el gate

- **WHEN** un turno queda esperando revisión humana y su respuesta parcial
  venía cortada por el tope
- **THEN** el aviso se muestra junto a esa respuesta parcial

# chunk-schema Delta Specification

## ADDED Requirements

### Requirement: La identidad de un chunk DEBE incluir su clase de fuente
Hoy el corpus tiene un solo tipo de documento, y a futuro va a tener otros que
todavía no están definidos. La identidad de una fila es
`(tenant_id, doc_version, source_type, content_hash)`.

`source_type` va en la clave única aunque tenga un solo valor porque es una
decisión **persistida**: agregarla después es migrar la clave de 57.101 filas,
hacer backfill y regenerar el corpus. Las decisiones que viven solo en código
—como qué chunker atiende qué formato— esperan al segundo tipo.

Ningún campo existente puede hacer ese trabajo: `document_kind`, `chunk_type` y
`transaction_type` discriminan DENTRO de una especificación funcional.

#### Scenario: Todo chunk declara su clase de fuente
- **WHEN** el chunker de especificaciones funcionales produce un chunk
- **THEN** su `source_type` es `functional_spec`, estampado explícitamente y no
  heredado del default

#### Scenario: La clase de fuente es identidad y no metadata
- **WHEN** una carga encuentra una fila existente con el mismo hash
- **THEN** actualiza las columnas de metadata y NO la clase de fuente

#### Scenario: Un corpus mixto se puede filtrar por clase de fuente
- **WHEN** se busca con `source_type` puesto
- **THEN** solo se devuelven chunks de esa clase
- **AND** sin `source_type` se buscan todas, porque filtrar al único valor que
  existe sería un no-op con aspecto de decisión

#### Scenario: El vocabulario de clases queda abierto
- **WHEN** aparezca un segundo tipo de fuente
- **THEN** basta usar un valor nuevo: el campo es un `str` y no un enum cerrado
  que habría que editar

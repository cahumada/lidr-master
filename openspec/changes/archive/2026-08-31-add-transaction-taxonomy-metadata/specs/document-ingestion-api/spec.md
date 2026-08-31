# document-ingestion-api Delta Specification

## MODIFIED Requirements

### Requirement: El contrato de respuesta DEBE estar completamente tipado
`metadata` y `stats` DEBEN ser modelos Pydantic anidados, no `dict` pelado. Un
`dict` pelado se renderiza como `object` vacío en la pestaña Schema de Swagger
y como placeholder genérico `additionalProp1` en Example Value, ocultando los
atributos reales a quien lea la documentación.

La respuesta DEBE llevar también una LISTA de documentos en vez de campos de
un solo documento, porque un archivo fuente puede describir varias transacciones.
Un archivo de una sola transacción produce una lista de uno, así los llamadores
tienen una sola forma que manejar en vez de dos.

#### Scenario: El schema expone atributos reales
- **WHEN** se genera el schema OpenAPI
- **THEN** `ChunkMetadata` declara `document_id`, `document_title`, `section`,
  `chunk_type`, `field` y `bullet_path`
- **AND** `IngestStats` declara `total_documents`, `total_chunks`,
  `total_tokens`, `table_chunks` y `narrative_chunks`

#### Scenario: Archivo de una sola transacción
- **WHEN** se ingesta un archivo que describe una transacción
- **THEN** la respuesta lleva `source_file` y una lista `documents` de una entrada
- **AND** `stats.total_documents` es 1

#### Scenario: Archivo multi-transacción
- **WHEN** se ingesta un archivo que describe una transacción y su compañera de solicitud de clave `_k`
- **THEN** `documents` lleva una entrada por transacción
- **AND** la entrada `_k` lleva `parent_transaction_code` nombrando su transacción principal

#### Scenario: Las stats reflejan los chunks producidos
- **WHEN** se ingesta un documento
- **THEN** `stats` reporta el total de chunks en todos los documentos, la suma de
  tokens, y la división entre chunks de tabla y narrativos

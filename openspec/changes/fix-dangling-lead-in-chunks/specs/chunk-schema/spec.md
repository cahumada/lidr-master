# chunk-schema Delta Specification

## ADDED Requirements

### Requirement: Un enunciado partido entre dos chunks DEBE quedar declarado en la metadata
Cuando el chunker no puede unir un enunciado en un solo chunk sin exceder el
techo de tokens, `ChunkMetadata` DEBE llevar el enlace hacia el vecino que lo
completa. Son dos campos opcionales de tipo `str | None`, planos como el resto
de la metadata porque el vector store filtra por igualdad:

| Campo | Tipo | Significado |
|---|---|---|
| `continued_from` | `str \| None` | `chunk_id` donde empieza el enunciado de este chunk |
| `continues_into` | `str \| None` | `chunk_id` donde termina el enunciado de este chunk |

Ambos apuntan siempre a un `chunk_id` del **mismo** `document_id` y la misma
sección: un enunciado no cruza documentos ni secciones. Su ausencia se lee
como "este chunk contiene un enunciado completo", que es el caso normal — la
misma semántica de ausencia que el resto de los campos opcionales del schema.

#### Scenario: Chunk enlazado hacia adelante
- **WHEN** el enunciado de un chunk continúa en el chunk siguiente
- **THEN** su metadata lleva `continues_into` con el `chunk_id` de ese chunk
- **AND** ese chunk lleva `continued_from` apuntando de vuelta

#### Scenario: Chunk con enunciado completo
- **WHEN** un chunk contiene un enunciado que abre y cierra en su propio texto
- **THEN** `continued_from` y `continues_into` están ausentes, no en cadena vacía

#### Scenario: El enlace no cruza documento ni sección
- **WHEN** un chunk lleva `continued_from` o `continues_into`
- **THEN** el `chunk_id` referido pertenece al mismo `document_id` y a la misma
  `section`

#### Scenario: Los campos aparecen en el schema OpenAPI
- **WHEN** se consulta el schema publicado en `/docs`
- **THEN** `continued_from` y `continues_into` figuran en `ChunkMetadata` como
  opcionales, con su descripción

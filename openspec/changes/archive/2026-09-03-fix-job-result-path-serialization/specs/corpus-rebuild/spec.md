# corpus-rebuild Delta Specification

## ADDED Requirements

### Requirement: El resultado de un paso DEBE ser serializable a JSON
`ingestion_jobs.result` es JSONB, y se escribe despues de CADA paso, no solo al
final. Un campo no serializable en el resultado de un paso —un `Path`, un
objeto interno del runner— hace fallar la escritura de progreso en cuanto ese
paso termina, aunque el paso en si haya sido exitoso.

#### Scenario: Un directorio resuelto se guarda como texto
- **WHEN** un paso reporta el directorio donde escribio o de donde leyo
- **THEN** el resultado que se persiste lleva ese directorio como string

#### Scenario: Los objetos internos no persisten
- **WHEN** un paso lleva objetos que existen solo para el reporte de consola
- **THEN** esos objetos no forman parte del resultado que se escribe en la fila
  del job

# corpus-rebuild Delta Specification

## ADDED Requirements

### Requirement: La fuente de los documentos DEBE ser intercambiable
Los documentos pueden estar en un directorio local o en un bucket
S3-compatible. El chunking necesita dos cosas de una fuente y no un sistema de
archivos: los documentos agrupados por módulo, y el texto de uno.

Esta abstracción entra ahora y no antes porque **entró la segunda fuente**. La
regla del proyecto —«una abstracción con una única implementación es ruido, se
agrega cuando entre la segunda estrategia»— se cumple, no se elude.

#### Scenario: Un directorio local
- **WHEN** la fuente es un directorio
- **THEN** los documentos se agrupan por su directorio de primer nivel

#### Scenario: Un bucket S3-compatible
- **WHEN** la fuente es un bucket
- **THEN** los documentos se agrupan por el primer segmento de su clave, porque
  S3 no tiene directorios y la pertenencia a un módulo es un prefijo

#### Scenario: Las dos fuentes producen lo mismo
- **WHEN** el mismo conjunto de documentos se trocea desde un directorio y
  desde un bucket
- **THEN** se producen los mismos chunks

#### Scenario: El corpus declara de dónde salió
- **WHEN** se escribe el manifiesto
- **THEN** lleva la fuente, porque un corpus sin procedencia no se puede
  rastrear

#### Scenario: La fuente se elige por la configuración
- **WHEN** hay un bucket configurado
- **THEN** se usa el bucket
- **AND** si no, el directorio local

### Requirement: Un listado de bucket DEBE leerse completo o fallar
`list_objects_v2` devuelve como máximo 1.000 claves por página y el corpus tiene
2.169 documentos. Un listado a medias no es un corpus más chico: es un corpus
al que le faltan reglas de negocio sin que nadie se enteró.

#### Scenario: Se pagina
- **WHEN** el bucket tiene más claves que una página
- **THEN** se piden todas las páginas

#### Scenario: Un listado truncado sin token es un error
- **WHEN** la respuesta dice que está truncada y no trae token de continuación
- **THEN** se levanta un error en lugar de devolver lo que llegó

### Requirement: Un documento ilegible NO DEBE abortar la corrida
Son 2.169 documentos de un export real. Uno con un byte inválido, o una clave
que el bucket no devuelve, se reporta y la corrida sigue.

#### Scenario: Un byte inválido
- **WHEN** un documento no decodifica como UTF-8
- **THEN** se decodifica reemplazando lo inválido y se trocea

#### Scenario: Una lectura que falla
- **WHEN** leer un documento lanza
- **THEN** se registra entre los archivos fallidos y la corrida sigue con el
  resto

#### Scenario: Una clave sin módulo
- **WHEN** una clave del bucket no tiene un segmento de módulo
- **THEN** se reporta y se saltea, en lugar de adivinarle uno

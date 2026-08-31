# document-chunking Delta Specification

## ADDED Requirements

### Requirement: Un chunk sin información NO DEBE producirse
Un chunk cuyo contenido es estructura markdown sobrante (`###  Proceso`, `#`),
un artefacto del export (`__`), o una fila de tabla con todas sus celdas
vacías, no aporta nada al retrieval y compite con contenido real.

El discriminador es el **contenido, no el largo**. `No aplica.`,
`A petición del usuario.` y `Volver a ejecutar.` son cortos pero son respuestas
reales: con su header contextual dicen "la frecuencia de ejecución de CPL500 es:
a petición del usuario". Descartar por largo habría borrado 291 respuestas
reales junto con el ruido — el mismo error que habría sido filtrar los
encabezados de las tablas rotas en vez de repararlas.

Un heading cuenta como estructura solo cuando su texto es una etiqueta corta: el
export también emite `# ` para líneas de continuación de bullets que sí llevan
contenido (`# § _Se construye el auxiliar concatenando..._`).

#### Scenario: Heading sobrante o artefacto
- **WHEN** el contenido de una unidad es solo un heading con etiqueta corta, o
  solo guiones bajos y puntuación
- **THEN** no se produce chunk

#### Scenario: Fila de tabla con todas sus celdas vacías
- **WHEN** una fila renderizada tiene todos sus valores vacíos
- **THEN** no se produce chunk, porque no hay información que perder

#### Scenario: Contenido corto pero real
- **WHEN** el contenido es una respuesta breve como `No aplica.`
- **THEN** el chunk se produce

#### Scenario: Línea con `#` que lleva contenido
- **WHEN** una línea empieza con `#` pero su texto es una regla y no una etiqueta
- **THEN** el chunk se produce

# document-chunking Delta Specification

## MODIFIED Requirements

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

La prueba de la fila vacía exige **al menos dos líneas**. Una fila renderizada
lleva una línea por columna, así que una única línea nunca es una fila: es
prosa, y la prosa que termina en dos puntos es un lead-in real. Sin ese piso, la
prueba borraba `La tabla es de valores variables. Algunos posibles valores son:`
en cinco secciones `Valores posibles`, porque al repararse la tabla que venía
abajo esa frase quedaba sola en la parte narrativa.

#### Scenario: Heading sobrante o artefacto
- **WHEN** el contenido de una unidad es solo un heading con etiqueta corta, o
  solo guiones bajos y puntuación
- **THEN** no se produce chunk

#### Scenario: Fila de tabla con todas sus celdas vacías
- **WHEN** una fila renderizada de dos o más columnas tiene todos sus valores vacíos
- **THEN** no se produce chunk, porque no hay información que perder

#### Scenario: Contenido corto pero real
- **WHEN** el contenido es una respuesta breve como `No aplica.`
- **THEN** el chunk se produce

#### Scenario: Línea con `#` que lleva contenido
- **WHEN** una línea empieza con `#` pero su texto es una regla y no una etiqueta
- **THEN** el chunk se produce

#### Scenario: Prosa de una sola línea que termina en dos puntos
- **WHEN** el contenido es una única línea como `Algunos posibles valores son:`
- **THEN** el chunk se produce, porque una línea sola no es una fila de tabla

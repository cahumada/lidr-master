# table-repair Delta Specification

## ADDED Requirements

### Requirement: La forma sin pipes DEBE reconstruirse como tabla
Una tercera forma rota aparece en el corpus: una corrida de N headings `####`
que son las columnas, seguida de un bloque por fila donde la etiqueta de la
fila es otro `#### <etiqueta>` y sus valores son prosa pelada, **sin ningún
`|`**. Las dos formas ya soportadas exigen pipes en las líneas de datos, así
que esta no dispara ninguna reparación y la sección termina chunkeada como
narrativa: cada celda queda en su propio chunk, sin nada que diga a qué fila
pertenece.

En `MER001` esto convierte una tabla de 4 columnas y ~48 filas en 191 chunks
sueltos; en las secciones `Campos` deja la descripción de cada campo separada
de su nombre, de modo que el nombre no está ni en el texto ni en
`metadata.field`. Son reglas de negocio de seguros perdidas en silencio.

La reconstrucción produce una tabla markdown válida de N columnas, que el
chunker ya sabe trocear una fila por chunk.

#### Scenario: Corrida de headers seguida de bloques etiqueta + prosa
- **WHEN** un bloque abre con N headings `####` consecutivos y sigue con bloques
  de `#### <etiqueta>` más prosa, sin ningún `|`
- **THEN** los N headings se vuelven la fila de encabezado más su separador `---`
- **AND** cada bloque siguiente se vuelve una fila con su etiqueta en la
  primera celda

#### Scenario: Catálogo de campos recuperable por nombre
- **WHEN** una sección `Campos` con esta forma se repara
- **THEN** cada campo produce un chunk de tipo `table` con su nombre en
  `metadata.field`
- **AND** el nombre del campo aparece en el texto del chunk junto a su descripción

### Requirement: Ante la duda NO se repara, y se advierte
`####` también es un subtítulo legítimo, y una reparación equivocada inventaría
filas — un error peor que no reparar, porque una fila inventada afirma una
regla de negocio que el documento no dice. La reparación DEBE exigir que los
bloques que siguen a la corrida de headers tengan estructura repetida y
consistente con el número de columnas.

Una corrida de headers que la guarda rechaza NO DEBE pasar en silencio: se
registra con su documento y su sección en el reporte de chunking, para que una
tabla que se sigue perdiendo sea visible en vez de invisible.

#### Scenario: Headings genuinos seguidos de prosa libre
- **WHEN** una corrida de `####` va seguida de prosa sin estructura repetida
- **THEN** no se repara nada y el texto vuelve byte por byte igual

#### Scenario: Corrida rechazada por la guarda
- **WHEN** la guarda rechaza una corrida que tiene la forma pero no la simetría
- **THEN** queda registrada en el reporte de chunking con documento y sección

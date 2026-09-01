# table-repair Delta Specification

## ADDED Requirements

### Requirement: La forma sin pipes DEBE reconstruirse como tabla
Una cuarta forma rota aparece en el corpus: N headings `####` que son las
columnas, seguidos de una fila por bloque donde la etiqueta de la fila es otro
`####` y sus valores son prosa pelada, **sin ningún `|`**. Las tres formas ya
soportadas exigen pipes en las líneas de datos, así que esta no dispara ninguna
reparación y la sección termina troceada como narrativa: cada celda queda en su
propio chunk, sin nada que diga a qué fila pertenece.

En las secciones `Campos` esto deja la descripción de cada campo separada de su
nombre, de modo que el nombre no está ni en el texto ni en `metadata.field` —
`cp001.md` emitía la descripción de `Moneda` sin la palabra `Moneda` en ningún
lado. Son reglas de negocio de seguros perdidas en silencio.

El discriminador entre un encabezado de columna y una etiqueta de fila es la
**itálica**: el corpus escribe `Título` / `Descripción` sin marcar y `_Moneda_`
en itálica. Sin esa distinción, la corrida `Título` / `Descripción` /
`_Parte repetitiva_` se leería como tres columnas en vez de dos columnas más un
divisor de grupo.

La reconstrucción produce una tabla markdown válida de N columnas, que el
chunker ya sabe trocear una fila por chunk. Corre como una segunda pasada, sobre
las regiones que las tres formas con pipes no reclamaron, así que el
comportamiento de esas tres no cambia.

#### Scenario: Corrida de headers seguida de bloques etiqueta + prosa
- **WHEN** un bloque abre con N headings `####` no itálicos y sigue con bloques
  de `#### _etiqueta_` más prosa, sin ningún `|`
- **THEN** los N headings se vuelven la fila de encabezado más su separador `---`
- **AND** cada bloque siguiente se vuelve una fila con su etiqueta en la
  primera celda

#### Scenario: Catálogo de campos recuperable por nombre
- **WHEN** una sección `Campos` con esta forma se repara
- **THEN** cada campo produce un chunk de tipo `table` con su nombre en
  `metadata.field`
- **AND** el nombre del campo aparece en el texto del chunk junto a su descripción

#### Scenario: Un miembro itálico de la corrida es etiqueta, no columna
- **WHEN** la corrida es `Título` / `Descripción` / `_Parte repetitiva_`
- **THEN** la tabla tiene dos columnas, no tres
- **AND** `Parte repetitiva` queda como una fila solo-etiqueta, sin descartarse

#### Scenario: El pipe que sobró de una línea de continuación
- **WHEN** una línea de valor abre con el separador de celda que dejó el export
  (`| Se incluye la agencia...`)
- **THEN** ese pipe se trata como separador y no como parte del texto

### Requirement: Ante la duda NO se repara, y se registra
`####` también es un subtítulo legítimo, y una reparación equivocada inventaría
filas — un error peor que no reparar, porque una fila inventada afirma una regla
de negocio que el documento no dice. La reparación DEBE exigir que cada fila
aporte exactamente un valor por columna que no sea la etiqueta, o ninguno; una
tabla de dos columnas es el caso trivial, donde todo lo que está bajo la
etiqueta es la única celda de descripción.

Rellenar una fila corta al final pondría el valor bajo el encabezado
equivocado: en `mer001.md` la bandera `Temporal` caería bajo `Tipo de Raíz del
Error`. Una fila sin reparar es un hueco; una fila mal reparada es una mentira.

Una corrida que la guarda rechaza NO DEBE pasar en silencio: se registra con sus
encabezados y su cantidad de filas, para que una tabla que se sigue perdiendo
sea visible en vez de invisible.

#### Scenario: Headings genuinos seguidos de prosa libre
- **WHEN** una corrida de `####` va seguida de prosa sin estructura repetida
- **THEN** no se repara nada y el texto vuelve byte por byte igual

#### Scenario: Filas que no se alinean con las columnas
- **WHEN** una tabla de más de dos columnas tiene filas con distinta cantidad de
  valores, como `mer001.md`
- **THEN** el bloque no se repara
- **AND** queda registrado con sus encabezados y la razón del rechazo

### Requirement: Una celda DEBE partirse solo por un pipe sin escapar
`_render_table` escapa como `\|` un pipe que pertenece al texto de una celda, y
una fila del corpus lo escapa a mano (`op008.md`: "posterior o igual a la fecha
\|de emisión del cheque"). Partir por cada pipe cortaba esas celdas en dos y
descartaba lo que caía más allá de la última columna, así que el renderizado y
el parseo tienen que coincidir: uno escapa y el otro desescapa.

#### Scenario: Pipe escapado dentro de una celda
- **WHEN** una fila renderizada lleva `\|` dentro del texto de una celda
- **THEN** la celda se parsea entera, con el `|` literal en su texto
- **AND** la fila conserva exactamente la cantidad de celdas de su tabla

## MODIFIED Requirements

### Requirement: Broken table blocks SHALL be reconstructed as valid markdown
Three broken shapes carry a pipe in their body, and all SHALL be reconstructed
into a single valid markdown table with a header row and a `---` separator row,
so the chunker sees one table instead of orphaned headings and pipe-bearing
lines. Las dos primeras se describen acá; la de filas multi-línea y la cuarta,
sin ningún pipe, tienen cada una su propio requirement más abajo.

The **simple** shape is two or more `####` headers followed by data rows, each
row a `label |  value` line (e.g. CA014 "Ramos generales"/"Vida", CA001 "Tipo
de registro / Transacción").

The **paired** shape is two `####` headers for the real columns, then each
row's label as its own `####` heading followed by a `|  value` line with no
left cell (e.g. CA001 "Tipo de inicio de vigencia / Fecha a mostrar").

#### Scenario: Simple shape
- **WHEN** a block opens with two or more consecutive `####` headers and every
  following non-blank line carries a `|` and is not a separator row
- **THEN** the `####` headers become the header row plus a `---` separator row
- **AND** each following line becomes a data row

#### Scenario: Paired shape
- **WHEN** the first two `####` headers are followed by further `####` headings
  each paired with a `|  value` line
- **THEN** the first two headers become the table's two columns
- **AND** each subsequent heading becomes a row label with its paired value as
  the second cell

#### Scenario: Surrounding content is untouched
- **WHEN** a repaired block sits between ordinary prose or bullets
- **THEN** the text before and after the block is returned byte-for-byte unchanged

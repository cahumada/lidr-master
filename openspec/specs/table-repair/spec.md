# table-repair Specification

## Purpose
Normalize the raw markdown of a functional-spec document and repair a
recurring export defect where a table lost its separator row and had its
column headers exported as `####` headings. Implemented in
`app/generation/rag/chunking/normalizer.py`. Without this, affected tables are
either invisible to the chunker or merged into unrelated prose — and these are
insurance business rules, so a lost cell is a defect, not cosmetic.

## Requirements

### Requirement: Line endings SHALL be normalized before any parsing
Source documents are Windows exports carrying `\r\n`. Every downstream parser
assumes `\n`, so normalization SHALL happen before any structural parsing.

#### Scenario: Windows line endings
- **WHEN** `normalize_line_endings` receives text containing `\r\n` or a bare `\r`
- **THEN** it returns the same text with every line ending as `\n`

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
### Requirement: A real heading SHALL NOT be mistaken for a broken table
`####` is also used for genuine subheadings. Repair SHALL trigger only when
the consecutive-headers run is immediately followed by pipe-bearing data
lines, so ordinary prose under a heading is never rewritten.

#### Scenario: Heading followed by prose
- **WHEN** one or more `####` headings are followed by ordinary paragraphs with no `|`
- **THEN** no repair is performed and the text is returned unchanged

### Requirement: A row with missing cells SHALL be padded and SHALL warn
A data row can carry fewer cells than there are headers. Dropping the row or
the missing cell silently would lose a business rule, so the row SHALL be kept,
padded with empty strings, and a warning SHALL be emitted — both to the
`structlog` logger and onto the repair's own record.

#### Scenario: Row shorter than the header count
- **WHEN** a data row has fewer cells than the reconstructed table has headers
- **THEN** the missing cells are filled with `""`
- **AND** a warning naming the offending row is emitted via `structlog`
- **AND** that warning is recorded in the returned `RepairedTable.warnings`

#### Scenario: Row label with no value line (paired shape)
- **WHEN** a `####` row label has no `|  value` line after it
- **THEN** its value cell is filled with `""` and a warning naming the label is emitted

### Requirement: Each repair SHALL remain traceable to its original block
Rewriting the source in place would erase the evidence of what was repaired.
Every repair SHALL return a record carrying the original raw block alongside
the reconstruction, so a reviewer can audit any transformation after the fact.

#### Scenario: Repair record
- **WHEN** `repair_broken_tables_with_trace` repairs a block
- **THEN** it returns a `RepairedTable` carrying `raw_original`,
  `repaired_markdown`, `headers` and `warnings`

#### Scenario: Text-only convenience wrapper
- **WHEN** the caller needs only the repaired text
- **THEN** `repair_broken_tables` returns the repaired text and discards the trace

### Requirement: Una tabla rota con filas multi-línea DEBE reconstruirse
Una tercera forma rota aparece en el corpus: N encabezados `####` seguidos de
filas que abarcan varias líneas. La primera celda de una fila queda sola, **sin
ningún pipe**, y el resto continúa en líneas que empiezan con `|`.

Son condiciones de búsqueda (tabla/campo/operador/valor) y reglas de validación
con su código de error — 365 bloques en 208 archivos. Antes de soportar esta
forma, sus encabezados quedaban como chunks sueltos y las reglas destrozadas.

El discriminador contra prosa normal bajo un `####` real es tenso: la línea sin
pipe DEBE estar seguida inmediatamente por una que empiece con `|`.

#### Scenario: Fila partida en tres líneas
- **WHEN** un bloque tiene 5 encabezados `####` y una fila cuya primera celda
  está sola, la segunda en una línea `|  valor` y el resto en `| a | b | c`
- **THEN** las cinco celdas caen en su columna correspondiente

#### Scenario: Filas de una y de varias líneas en el mismo bloque
- **WHEN** un bloque mezcla filas completas en una línea con filas partidas
- **THEN** ambas se reconstruyen correctamente

#### Scenario: Regla de validación con su código de error
- **WHEN** un bloque tiene una regla en una línea y su código en la siguiente
  (`Debe incluir el ejercicio` / `| 736024`)
- **THEN** quedan en la misma fila, regla y código en su columna

#### Scenario: Prosa bajo un heading real sigue intacta
- **WHEN** un `####` real está seguido de prosa que no continúa con `|`
- **THEN** no se repara nada

### Requirement: La forma pareada DEBE reconocerse por su alternancia, no por sus dos primeras líneas
La forma pareada tiene, después de sus dos encabezados de columna reales, una
etiqueta `####` por fila. Reconocerla solo por sus dos primeras líneas hacía que
una tabla de 5 columnas con filas partidas se leyera como una pareada de 2,
convirtiendo tres de sus encabezados de columna en filas.

Una corrida de encabezados iniciales cuya cola NO tiene encabezados es la forma
simple o la de filas multi-línea, no la pareada.

#### Scenario: Tabla de 5 columnas con filas partidas
- **WHEN** se repara un bloque con 5 encabezados consecutivos y ninguno en su cola
- **THEN** los cinco quedan como columnas
- **AND** ninguno se convierte en fila

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

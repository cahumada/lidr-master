# document-chunking Delta Specification

## ADDED Requirements

### Requirement: Un patrón de heading NO DEBE cruzar el fin de línea
`re.MULTILINE` cambia dónde anclan `^` y `$`, pero no impide que `\s+` consuma
un `\n`. Con `^##\s+(.+?)\s*$`, un heading vacío se traga la línea siguiente y
la usa como su propio nombre.

El separador entre el marcador `#` y el texto DEBE ser espacio u horizontal
tab, nunca un salto de línea.

#### Scenario: Heading vacío seguido de un heading real
- **WHEN** el fuente tiene una línea `##` sin texto y después `## Notas al programador`
- **THEN** se produce una sección llamada `Notas al programador`
- **AND** ninguna sección se llama `## Notas al programador`

#### Scenario: Heading vacío seguido de prosa
- **WHEN** una línea `##` sin texto va seguida de un párrafo del cuerpo
- **THEN** no se crea ninguna sección con ese párrafo por nombre
- **AND** el párrafo queda en la sección que lo contenía

#### Scenario: Título vacío seguido del título real
- **WHEN** una línea `#` sin texto precede al `# Título` del documento
- **THEN** el título del documento es `Título`, sin el marcador

### Requirement: El nombre de un heading DEBE ser su texto humano, sin el marcado del export
`metadata.section` es un campo filtrable y el header contextual se embebe. El
marcado del export de Word —marcadores de énfasis partidos, sintaxis de link,
glifos de viñeta, escapes con barra— no es parte del nombre.

La misma sección llegó a existir en tres grafías (`Proceso****Batch`,
`Proceso** Batch`, `Proceso********Batch`), ninguna de las cuales agrupa con el
`Proceso batch` de los otros 2.100 documentos.

#### Scenario: Énfasis partido entre dos corridas en negrita
- **WHEN** un heading es `## **Función****General**`
- **THEN** su nombre es `Función General`

#### Scenario: Un guion bajo dentro de una palabra NO es énfasis
- **WHEN** un heading es `## Conteo de unidades por unit_type`
- **THEN** su nombre conserva `unit_type` intacto

Es la regla de CommonMark: `foo_bar_baz` no lleva énfasis, `a*b*c` sí. Sin esa
distinción, limpiar el énfasis rompe los identificadores del dominio.

#### Scenario: Un heading que es un link
- **WHEN** un heading es `## [Campos](../../seguridad/valschemaoffice.html)`
- **THEN** su nombre es `Campos`, sin la URL

#### Scenario: Un heading que abre con un glifo de viñeta de Word
- **WHEN** un heading es `## o _Ramo \(parámetro\)._`
- **THEN** su nombre es `Ramo (parámetro).`

#### Scenario: El bullet_path tampoco lleva marcadores
- **WHEN** un elemento del `bullet_path` viene de una línea `### **Modo de generación**`
- **THEN** en el header contextual aparece como `Modo de generación`

### Requirement: Limpiar el nombre de un heading NUNCA DEBE hacer que se pierda su cuerpo
Un heading cuyo nombre queda vacío o degenerado se descarta como *junk*, y
descartarlo se lleva su cuerpo. Limpiar el marcado puede convertir en junk a un
heading que antes tenía nombre: `## [](../mantenimiento/ma0085.html)` — un link
cuya etiqueta perdió el export — limpiaba a la cadena vacía y **se llevó las
siete reglas de validación de MS010 con sus códigos de error** (10208, 10209,
12039, 10885).

Cuando el nombre limpio queda vacío o es junk y el heading crudo era un link, el
destino del link es el único nombre que queda, así que ese es el nombre. Marcar
es mejor que borrar — el mismo principio que el resto del pipeline.

#### Scenario: Link sin etiqueta
- **WHEN** un heading es `## [](../mantenimiento/ma0085.html)`
- **THEN** su nombre es `MA0085`
- **AND** su cuerpo sigue produciendo chunks

#### Scenario: Link cuya etiqueta es un placeholder
- **WHEN** un heading es `## [.](../seguridad/valschemaoffice.html)`
- **THEN** su nombre es `VALSCHEMAOFFICE`, no `.`

#### Scenario: El corpus completo no pierde contenido
- **WHEN** se regenera el corpus con los nombres limpios
- **THEN** ningún fragmento de contenido desaparece: cada palabra que estaba en
  algún chunk sigue estando en algún chunk

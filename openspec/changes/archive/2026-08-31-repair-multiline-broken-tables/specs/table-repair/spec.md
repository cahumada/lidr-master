# table-repair Delta Specification

## ADDED Requirements

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

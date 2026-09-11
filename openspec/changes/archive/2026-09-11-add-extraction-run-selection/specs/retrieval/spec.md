# retrieval Delta Specification

## MODIFIED Requirements

### Requirement: El contexto DEBE advertir cuando la evidencia no está contemplada
Un bloque de evidencia que describe una transacción a la que hoy no se puede
acceder, presentado igual que una vigente, produce una respuesta que afirma de
más sobre reglas de negocio de seguros. El modelo tiene que poder saberlo, y por
eso la advertencia va **adentro** del bloque y no al lado.

La advertencia usa el **estado declarado** y nunca la palabra "baja": el catálogo
dice "acceso restringido", que no es lo mismo, y decir lo segundo sería inventar.

El estado se resuelve del **árbol de la corrida activa**, no de la columna
estampada en el chunk. Son dos cosas distintas: la columna es un hecho con la
procedencia de la corrida que la estampó, y el árbol es lo que vale al momento de
responder. Resolver del árbol hace que cambiar de corrida se refleje de inmediato
y por completo, sin re-estampar 56.537 filas ni dejar una ventana en la que las
respuestas mezclen dos corridas.

Se renderiza **solo** cuando el estado está resuelto y no es el activo. Un hit
vigente o sin estado se renderiza byte a byte como antes: `render_hit_block` es el
único renderer y `fit_to_budget` cuenta tokens sobre lo que devuelve, así que una
línea en todos los bloques costaría tokens en cada consulta y volvería
incomparable cada corrida del eval de fidelidad.

#### Scenario: Evidencia de una transacción no contemplada
- **WHEN** el árbol de la corrida activa resuelve para el documento del hit un
  estado distinto del activo
- **THEN** su bloque de evidencia incluye una línea con ese estado declarado
- **AND** el presupuesto de tokens cuenta esa línea

#### Scenario: Evidencia vigente o sin estado
- **WHEN** el árbol resuelve el estado activo, o no lo resuelve
- **THEN** el bloque renderizado es idéntico al que producía antes de este cambio

#### Scenario: Cambiar de corrida cambia la advertencia sin tocar el corpus
- **WHEN** se activa una corrida donde el estado de esa transacción es distinto
- **THEN** la advertencia del bloque cambia en la consulta siguiente
- **AND** la columna estampada en el chunk NO se modifica

#### Scenario: Sin corrida vigente, la columna estampada es el respaldo
- **WHEN** no hay ninguna corrida en vigor y por lo tanto no hay árbol activo
- **THEN** la advertencia se resuelve de la columna estampada en el chunk
- **AND** eso NO contradice la regla de arriba: si no hay corrida activa, no hay
  nada respecto de lo cual la columna esté vieja, y su procedencia está
  registrada en el sello del corpus. Lo que no debe pasar es que decida la
  columna **habiendo** árbol.

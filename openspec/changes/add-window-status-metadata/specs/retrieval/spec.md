# retrieval Delta Specification

## ADDED Requirements

### Requirement: Un hit DEBE llevar el estado de la ventana que trae su metadata
La spec ya exige que cada resultado diga de dónde vino. El estado de la ventana
es parte de esa procedencia: 574 documentos del corpus describen transacciones que
el sistema fuente no contempla, y un hit que no lo declara obliga a cada
consumidor —la consola, el orquestador, el sintetizador— a adivinarlo o a
ignorarlo.

Viaja como el resto de la metadata filtrable: texto plano, opcional, y ausente
cuando el árbol no lo resuelve.

#### Scenario: El estado viaja en el resultado
- **WHEN** un chunk cuyo `window_status` está resuelto entra en los resultados
- **THEN** el hit lo declara con el nombre declarado por el catálogo

#### Scenario: Estado no resuelto
- **WHEN** el chunk no tiene estado resuelto
- **THEN** el hit lo deja ausente
- **AND** ningún consumidor DEBE interpretar esa ausencia como "activo"

### Requirement: El contexto DEBE advertir cuando la evidencia no está contemplada
Un bloque de evidencia que describe una transacción a la que hoy no se puede
acceder, presentado igual que una vigente, produce una respuesta que afirma de
más sobre reglas de negocio de seguros. El modelo tiene que poder saberlo, y por
eso la advertencia va **adentro** del bloque y no al lado.

La advertencia usa el **estado declarado** y nunca la palabra "baja": el catálogo
dice "acceso restringido", que no es lo mismo, y decir lo segundo sería inventar.

Se renderiza **solo** cuando el estado está resuelto y no es el activo. Un hit
vigente o sin estado se renderiza byte a byte como antes: `render_hit_block` es el
único renderer y `fit_to_budget` cuenta tokens sobre lo que devuelve, así que una
línea en todos los bloques costaría tokens en cada consulta y volvería
incomparable cada corrida del eval de fidelidad.

#### Scenario: Evidencia de una transacción no contemplada
- **WHEN** un hit tiene `window_status` resuelto y distinto del activo
- **THEN** su bloque de evidencia incluye una línea con ese estado declarado
- **AND** el presupuesto de tokens cuenta esa línea

#### Scenario: Evidencia vigente o sin estado
- **WHEN** el hit está activo, o su estado no está resuelto
- **THEN** el bloque renderizado es idéntico al que producía antes de este cambio

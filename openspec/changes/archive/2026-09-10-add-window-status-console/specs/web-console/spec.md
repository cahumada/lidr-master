# web-console Delta Specification

## ADDED Requirements

### Requirement: La consola muestra el estado declarado cuando la ventana no está contemplada
La pantalla de búsqueda, las citas en vivo del chat y la vista previa
de ingesta SHALL renderizar `window_status` cuando el campo está
resuelto y su valor no es `Activo`. El texto SHALL ser el nombre
declarado por el catálogo (`Acceso restringido`, `En proceso de
instalación`), nunca la palabra "baja" ni el código crudo. Un hit,
una cita o un chunk vigente o sin estado SHALL NOT ganar un badge de
estado: la ausencia no se interpreta como vigente y no se inventa
una etiqueta "sin estado".

El campo viaja en el contrato ya expuesto por el servicio
(`SearchHit.window_status`, `ChunkMetadata.window_status`). La
consola SHALL espejarlo en `lib/ai-service/types.ts` antes de
leerlo. Un servicio que omite el campo SHALL degradar a no pintar
el badge, no a un error de parseo.

Un turno reabierto desde `history` SHALL NOT mostrar un estado
inventado: `CitationSnapshot` no lo trae. La consola SHALL NOT
filtrar por `window_status`: el servicio no acepta ese recorte, y
un query param ignorado se leería como exclusión.

#### Scenario: hit de una transacción no contemplada
- **WHEN** una búsqueda devuelve un hit con
  `window_status` = `Acceso restringido`
- **THEN** ese resultado muestra el texto `Acceso restringido`
- **AND** no muestra la palabra "baja"

#### Scenario: hit vigente o sin estado
- **WHEN** el hit trae `window_status` = `Activo`, o el campo está
  ausente
- **THEN** el resultado no muestra un badge de estado
- **AND** no afirma que la transacción esté vigente

#### Scenario: cita en vivo del chat
- **WHEN** un turno agentico en vivo completa y una cita trae
  `window_status` distinto de `Activo`
- **THEN** esa cita muestra el nombre declarado

#### Scenario: turno reabierto no inventa estado
- **WHEN** el operador reabre una conversación desde `history`
- **THEN** las citas de esos turnos no muestran un badge de estado
  salvo que el snapshot lo traiga

#### Scenario: vista previa de ingesta
- **WHEN** el operador sube un documento cuya ventana no está
  contemplada y el chunker estampa `window_status`
- **THEN** la vista previa muestra el nombre declarado
- **AND** no persiste el resultado

#### Scenario: no se finge un filtro
- **WHEN** el operador usa la pantalla de búsqueda o el chat
- **THEN** no hay un control que envíe `window_status` al BFF
- **AND** la consulta no recorta por estado

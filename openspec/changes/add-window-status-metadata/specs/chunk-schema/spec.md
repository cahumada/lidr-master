# chunk-schema Delta Specification

## ADDED Requirements

### Requirement: El estado de la ventana DEBE viajar declarado, no interpretado
`WINDOWS.SSTATREGT` declara el estado del registro, y su catálogo es `TABLE26`:
`1` Activo, `2` En proceso de instalación, `3` Acceso restringido. Que el sistema
fuente **solo contemple el `1`** es conocimiento del analista funcional, no algo
que el catálogo afirme.

Por eso `window_status` lleva el **nombre declarado** y nunca un booleano
derivado: colapsar el hecho con su interpretación haría imposible saber después
qué decía el dato, y permitiría que una respuesta afirme que una transacción "fue
dada de baja" cuando lo declarado es "acceso restringido" — que no es lo mismo.

El valor `4`, que no existe en el catálogo, es un error de datos conocido y se
resuelve como `3`, pero **contado y logueado**: 18 filas hoy, y si una corrida
futura trae más, eso tiene que verse. Un valor fuera del catálogo NO se normaliza
a nada.

#### Scenario: Estado declarado
- **WHEN** el árbol resuelve `SSTATREGT = '3'` para el código de un chunk
- **THEN** `window_status` es `Acceso restringido`
- **AND** no se emite ningún booleano ni ninguna palabra que el catálogo no declare

#### Scenario: El error de datos conocido
- **WHEN** el árbol encuentra `SSTATREGT = '4'`
- **THEN** el estado se resuelve como `Acceso restringido`
- **AND** la normalización queda contada en el log de carga del árbol

#### Scenario: Valor fuera del catálogo
- **WHEN** el estado no es `1`, `2`, `3` ni `4`
- **THEN** `window_status` está ausente
- **AND** no se elige ningún estado por defecto

#### Scenario: Sin fuente de estado
- **WHEN** el árbol se carga de un export que no trae la columna de estado
- **THEN** `window_status` está ausente en todos los chunks
- **AND** el resto de la metadata se comporta igual que antes

## MODIFIED Requirements

### Requirement: ChunkMetadata DEBE ser un modelo tipado con campos planos
Un campo tipado como `dict` se renderiza como `object` vacío en la pestaña
Schema de Swagger, ocultando sus atributos. Los campos del breadcrumb son
**planos y no anidados** porque el vector store filtra por igualdad, no por
recorrido de árbol.

| Campo | Presencia |
|---|---|
| `document_id`, `document_title`, `section`, `chunk_type` | siempre |
| `transaction_type`, `document_kind` | siempre (con default) |
| `field` | solo cuando `chunk_type='table'` |
| `bullet_path` | solo cuando `chunk_type='narrative'` |
| `module_code`, `module_name` | solo si el árbol `WINDOWS` resuelve camino |
| `submodule_code`, `submodule_name` | solo si el camino tiene ese nivel |
| `window_status` | solo si el árbol declara el estado del código |

#### Scenario: Chunk de fila de tabla
- **WHEN** se produce un chunk con `chunk_type='table'`
- **THEN** `field` lleva el valor de la primera columna de la fila
- **AND** `bullet_path` está ausente

#### Scenario: Chunk narrativo
- **WHEN** se produce un chunk con `chunk_type='narrative'` bajo bullets anidados
- **THEN** `bullet_path` lleva el breadcrumb de etiquetas hasta el chunk
- **AND** `field` está ausente

#### Scenario: section conserva el heading literal de la fuente
- **WHEN** se produce un chunk de cualquier sección
- **THEN** `section` lleva el texto del heading H2 tal como está en el documento,
  en español, sin traducir ni normalizar a una lista cerrada

#### Scenario: El estado de la ventana es un campo plano más
- **WHEN** se produce un chunk de una transacción cuyo estado el árbol resuelve
- **THEN** `window_status` viaja como texto plano, junto a `window_type_name`
- **AND** no se anida bajo ninguna estructura de estado

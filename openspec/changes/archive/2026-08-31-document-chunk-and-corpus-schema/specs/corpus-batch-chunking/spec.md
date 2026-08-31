# corpus-batch-chunking Delta Specification

## ADDED Requirements

### Requirement: El corpus generado DEBE tener una forma declarada en disco
`data/chunks/` es el artefacto que consumirá la capa de embeddings, así que su
forma es parte del contrato, no un detalle del script. Cada `<módulo>.json`
lleva dos claves de nivel raíz:

```json
{
  "module": "policies",
  "documents": [ { "source_file": "...", "module": "...", "...": "...", "chunks": [] } ]
}
```

Cada entrada de `documents` es un `ChunkedDocument` serializado más dos campos
de procedencia que el modelo no lleva, porque pertenecen a la corrida y no a la
transacción: `source_file` y `module`.

#### Scenario: Un JSON por módulo
- **WHEN** la corrida batch termina
- **THEN** existe un `<out>/<módulo>.json` por módulo procesado
- **AND** cada uno lleva `module` y `documents`

#### Scenario: Procedencia en cada documento
- **WHEN** se escribe una entrada de documento
- **THEN** lleva `source_file` y `module` además de los campos del `ChunkedDocument`
- **AND** los campos de taxonomía (`transaction_type`, `document_kind`,
  `child_links`, `navigation_path`, `is_menu_node`, `parent_transaction_code`,
  `is_container`) se persisten, no solo la metadata de los chunks

### Requirement: Un archivo fuente DEBE poder aportar varias entradas de documento
La salida se agrupa por transacción, no por archivo: un archivo que describe una
transacción y su acompañante `_k` aporta dos entradas con el mismo
`source_file`. Un consumidor que asuma una entrada por archivo va a perder
transacciones.

#### Scenario: Archivo multi-transacción
- **WHEN** un archivo declara dos transacciones
- **THEN** aporta dos entradas de `documents`, con el mismo `source_file` y
  distinto `document_id`

### Requirement: El artefacto de entrada del árbol DEBE ser un CSV declarado
El árbol de navegación entra al pipeline como `data/windows_tree.csv`, con tres
columnas: `code`, `parent_code`, `description`. Es la conversión de un export de
la tabla `WINDOWS`, reproducible con `scripts/import_windows_tree.py`.

El CSV es un artefacto de datos versionado, no un cache: es una foto parcial de
una instalación, y su alcance limita cuánto breadcrumb resuelve.

#### Scenario: Columnas del CSV
- **WHEN** el pipeline carga el árbol
- **THEN** lee `code`, `parent_code` y `description`
- **AND** una fila sin `code` se ignora

#### Scenario: Conversión reproducible
- **WHEN** se convierte el mismo export dos veces
- **THEN** el CSV resultante es idéntico

#### Scenario: Sin CSV
- **WHEN** el archivo no existe en la ruta configurada
- **THEN** la corrida procede sin resolver breadcrumb, sin fallar

## MODIFIED Requirements

### Requirement: La corrida DEBE emitir un reporte que nombre cada anomalía
Los conteos solos esconderían los dos modos de falla que ameritan la atención
de una persona: un archivo que parseó pero no produjo nada, y un archivo que
lanzó excepción. Ambos DEBEN listarse individualmente por ruta, no solo
totalizarse.

El reporte DEBE incluir además el conteo de documentos, que puede ser mayor que
el de archivos: la diferencia son las transacciones que estaban escondidas
dentro de archivos multi-transacción, y es un dato de cobertura, no un error de
suma.

#### Scenario: Contenido del reporte
- **WHEN** la corrida termina
- **THEN** `<out>/chunking_report.md` lleva una tabla por módulo con archivos,
  documentos, chunks, tokens y el split tabla/narrativa
- **AND** cada archivo con cero chunks se lista por ruta con su `document_id` resuelto
- **AND** cada archivo fallido se lista por ruta con su error

#### Scenario: Más documentos que archivos
- **WHEN** un módulo tiene archivos multi-transacción
- **THEN** su conteo de documentos es mayor que el de archivos, y eso es correcto

#### Scenario: Archivo con cero chunks se expone, no se acepta en silencio
- **WHEN** un archivo no produce chunks
- **THEN** se cuenta y se lista en el reporte para revisión

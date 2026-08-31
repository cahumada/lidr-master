# chunk-schema Specification

## Purpose
El contrato de datos que produce el chunking y consumirán las capas de
embeddings y persistencia: `Chunk`, `ChunkMetadata`, `Reference` y
`ChunkedDocument`, con sus invariantes y la semántica de cada campo
opcional. Definido en `app/generation/rag/schemas.py` y publicado en el
schema OpenAPI del servicio.

## Requirements

### Requirement: Un chunk DEBE llevar texto embebible, metadata filtrable y su conteo de tokens
`Chunk` es la unidad que la capa de embeddings va a consumir. Sus cuatro
campos tienen roles distintos que no se mezclan: `text` es lo que se embebe,
`metadata` lo que se filtra sin embeber, `token_count` el presupuesto medido, y
`references` la evidencia de relaciones con otros documentos.

| Campo | Tipo | Rol |
|---|---|---|
| `chunk_id` | `str` | Identificador trazable y único |
| `text` | `str` | Header contextual + contenido; **es lo que se embebe** |
| `metadata` | `ChunkMetadata` | Campos filtrables, **no** embebidos |
| `token_count` | `int` (≥0) | Tokens de `text`, header incluido |
| `references` | `list[Reference]` | Referencias cruzadas halladas en `text` |

#### Scenario: Forma de un chunk producido
- **WHEN** el chunker produce cualquier chunk
- **THEN** lleva los cinco campos, con `references` como lista (vacía si no hay)
- **AND** `metadata` es un modelo tipado, no un `dict` de forma libre

### Requirement: chunk_id DEBE tener formato trazable y ser único dentro del archivo
El formato es `{document_id}::{section_slug}::{índice}`. El slug se deriva del
heading en español de la sección (ASCII, minúscula, guiones bajos), no de una
tabla de traducción mantenida a mano: los headings son abiertos entre los 30
módulos y un diccionario fijo falla en silencio con cada heading nuevo.

Todo lo atribuido a un mismo `document_id` DEBE compartir un único contador por
slug. Numerar cada bloque desde 1 de forma independiente produjo 952 `chunk_id`
duplicados en 223 archivos.

#### Scenario: Formato
- **WHEN** se produce un chunk de la sección `Función` de `CA014`
- **THEN** su `chunk_id` tiene la forma `CA014::funcion::1`

#### Scenario: Unicidad dentro de un archivo fuente
- **WHEN** un archivo aporta varias transacciones, o un preámbulo y un bloque
  resuelven al mismo `document_id`
- **THEN** ningún par de chunks del archivo comparte `chunk_id`

### Requirement: text DEBE incluir el header contextual, y token_count DEBE medirlo
`text` se prefija con el documento y la sección, para que un chunk recuperado
solo diga de qué transacción y sección viene. `token_count` DEBE contar ese
texto **completo, header incluido**, medido con el tokenizer del modelo de
embeddings (`tiktoken`, `text-embedding-3-small`) — un presupuesto que ignore
el header subestima lo que se manda a embeber.

#### Scenario: Header presente
- **WHEN** se produce cualquier chunk
- **THEN** `text` empieza con `[Documento: {document_id} - {document_title}]`
- **AND** la línea siguiente es `[Sección: {section}]`, o
  `[Sección: {section} > {bullet_path}]` cuando hay breadcrumb de bullets

#### Scenario: token_count consistente
- **WHEN** se produce cualquier chunk
- **THEN** `token_count` es igual al conteo del tokenizer sobre su `text` completo

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

### Requirement: Un campo opcional ausente DEBE leerse como no resuelto, nunca como vacío
Los campos opcionales de la metadata no son "datos faltantes que alguien
debería completar": significan que la información no está disponible. El export
de `WINDOWS` resuelve camino para el 54,2% de los documentos, y el 45,8%
restante no tiene módulo *conocido*, no un módulo *vacío*. Un consumidor no
DEBE rellenarlos ni tratarlos como cadena vacía.

#### Scenario: Breadcrumb no resuelto
- **WHEN** el código de un documento no está en el árbol, o su cadena de padres
  no llega a la raíz
- **THEN** `module_code`, `module_name`, `submodule_code` y `submodule_name`
  están ausentes
- **AND** ningún valor se fabrica para rellenarlos

#### Scenario: Tipo no clasificable
- **WHEN** ninguna regla de nomenclatura matchea el código
- **THEN** `transaction_type` es `unknown`
- **AND** el documento lleva la razón en `transaction_type_reason`

### Requirement: Reference DEBE usar un discriminador de tipo, y nunca apuntar al propio documento
El corpus tiene dos patrones de referencia distintos, y viajan en **una** lista
de objetos con discriminador, no en dos listas paralelas: unificar el tipo en la
estructura evita que un consumidor tenga que saber cuál lista mirar.

| `type` | Patrón en la fuente |
|---|---|
| `inline_transaction` | transacción hermana entre backticks: `` `CA003` `` |
| `footnote_tag` | tag tipo nota al pie: `<DF009>` |

#### Scenario: Referencia con su contexto
- **WHEN** el texto de un chunk contiene una referencia de cualquiera de los dos patrones
- **THEN** se registra con su `code`, su `type` y el `context` de la línea donde aparece

#### Scenario: Sin auto-referencia
- **WHEN** el código referenciado es el `document_id` del propio chunk
- **THEN** no se registra referencia

### Requirement: ChunkedDocument DEBE representar UNA transacción, no un archivo
Un archivo fuente no siempre es una transacción: puede describir varias. Por eso
trocear un archivo devuelve una **lista** de `ChunkedDocument`, uno por
transacción encontrada, y un archivo de una sola devuelve una lista de un
elemento — un solo shape para el consumidor, no dos.

| Campo | Significado |
|---|---|
| `document_id`, `document_title` | identidad de la transacción |
| `parent_transaction_code` | para una `_k`, su transacción principal; solo si está declarada en el mismo archivo |
| `is_container` | el bloque describe la familia, no una transacción |
| `transaction_type` + `transaction_type_reason` | tipo, y por qué si es `unknown` |
| `document_kind` | `content` o `index` |
| `child_links` | códigos a los que enlaza, en orden |
| `navigation_path` | camino completo desde la raíz del menú, si resuelve |
| `is_menu_node` | `True` carpeta, `False` hoja, ausente si no se sabe |
| `chunks` | los chunks de esta transacción |

#### Scenario: Archivo de una transacción
- **WHEN** se trocea un archivo que describe una sola transacción
- **THEN** el resultado es una lista de un `ChunkedDocument`

#### Scenario: Archivo con transacción y su acompañante de clave
- **WHEN** se trocea un archivo que declara una transacción y su `_k`
- **THEN** el resultado lleva un `ChunkedDocument` por cada una
- **AND** el de la `_k` lleva `parent_transaction_code`

#### Scenario: is_menu_node distingue no-sabido de hoja
- **WHEN** no hay export de `WINDOWS` cargado, o el código no está en el árbol
- **THEN** `is_menu_node` está ausente, en vez de `False`

### Requirement: El contrato DEBE quedar visible en el schema OpenAPI
Estos modelos se publican en Swagger, así que las descripciones de sus campos
son documentación de cara al consumidor, no comentarios internos. Ningún campo
del contrato expuesto DEBE tiparse como `dict` pelado.

#### Scenario: Schema generado
- **WHEN** se genera el schema OpenAPI
- **THEN** `Chunk`, `ChunkMetadata`, `Reference` y `ChunkedDocument` declaran
  cada uno sus propiedades con nombre y tipo

### Requirement: Cada chunk DEBE llevar la identidad de versión de su corpus
Un cliente entrega documentación actualizada, y el despliegue es multi-cliente
(`deployment_mode: "saas"`). El manifiesto del corpus es la declaración
autoritativa, pero un vector store filtra **por fila**: sin `tenant_id` y
`doc_version` en la metadata del chunk no hay forma de aislar un cliente ni una
versión en una consulta.

Los defaults del modelo (`"default"` / `"unversioned"`) existen solo para que
las funciones de chunking no tengan que arrastrar estos campos por cinco
firmas. NUNCA deben sobrevivir a un chunk producido.

#### Scenario: Identidad estampada en cada chunk
- **WHEN** se produce cualquier chunk
- **THEN** su metadata lleva el `tenant_id` y el `doc_version` de la corrida

#### Scenario: Un documento que absorbe otro bloque
- **WHEN** un documento acumula chunks de más de un bloque (su preámbulo y su
  propio bloque)
- **THEN** todos sus chunks llevan el mismo estampado, incluidos tenant,
  versión, tipo y breadcrumb

#### Scenario: Mismo documento, dos clientes
- **WHEN** el mismo documento se trocea para dos `tenant_id` distintos
- **THEN** el `chunk_id` es el mismo —es un localizador, no una identidad—
- **AND** el `tenant_id` es lo que distingue las filas

### Requirement: content_hash DEBE identificar el contenido en dos niveles
Lo que no cambió no hay que volver a pagarlo. El hash de un **chunk** cubre
exactamente los bytes que se embeben (`text`, header incluido), así que un hash
igual entre corridas significa que el embedding existente sigue siendo válido.
El hash de un **documento** cubre su fuente normalizada, así que un documento
sin cambios se puede saltear entero.

El hash se calcula sobre el texto **normalizado**, así un re-export que solo
cambió los fines de línea no parece un cambio de contenido.

#### Scenario: Estable entre corridas
- **WHEN** se trocea el mismo contenido dos veces
- **THEN** los hashes de documento y de chunks son idénticos

#### Scenario: Cambios que la normalización absorbe
- **WHEN** el mismo documento llega con fines de línea de Windows
- **THEN** su `content_hash` de documento no cambia

#### Scenario: Reingesta incremental de un documento editado
- **WHEN** se edita una regla de un documento y se vuelve a trocear
- **THEN** el hash del documento cambia
- **AND** la gran mayoría de los hashes de sus chunks se mantiene, así que solo
  lo modificado necesita re-embeberse

#### Scenario: El hash del chunk cubre lo que se embebe
- **WHEN** se produce cualquier chunk
- **THEN** su `content_hash` es el SHA-256 de su `text` completo

### Requirement: La identidad física de un chunk DEBE ser la clave compuesta
`chunk_id` es un **localizador** dentro de un documento, y se mantiene estable
entre versiones a propósito, para poder comparar la misma posición. No es una
identidad única: la identidad física es `(tenant_id, doc_version, chunk_id)`.

Comparar versiones por `chunk_id` no es confiable —si una sección se corre de
lugar, los índices se desplazan y `CA014::validaciones::7` pasa a apuntar a
otra regla—; para comparar contenido está `content_hash`.

#### Scenario: Dos versiones del mismo documento
- **WHEN** se trocean dos `doc_version` del mismo documento
- **THEN** conviven sin colisionar, porque la versión forma parte de la clave

### Requirement: source_revision y valid_from DEBEN quedar ausentes si no se conocen
Vienen del control de revisión del cliente, que el markdown no lleva. Ausentes,
no fabricados. `valid_from` habilita preguntar qué decía una transacción en una
fecha pasada, cuando ese dato exista.

#### Scenario: Documento sin control de revisión propio
- **WHEN** se trocea un documento markdown del corpus
- **THEN** `source_revision` y `valid_from` quedan ausentes
- **AND** `content_hash` sí está, porque siempre es computable

# chunk-schema Delta Specification

## ADDED Requirements

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

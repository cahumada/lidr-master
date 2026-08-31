# document-chunking Delta Specification

## ADDED Requirements

### Requirement: Un archivo con varias transacciones DEBE atribuir cada chunk a su propia transacción
La relación archivo-transacción no siempre es uno a uno. Un documento puede
llevar varias transacciones, cada una como su propio bloque `# ` (H1) con su
bloque de id y su conjunto de secciones, separadas por headings placeholder
`## .` — verificado en `clients/bc005.md`, que lleva `BC005_k` y `BC005`.

Los chunks DEBEN atribuirse por bloque H1, resolviendo el id dentro de ese
bloque, para que una regla documentada bajo una transacción nunca se conteste
bajo otra.

#### Scenario: Dos transacciones en un archivo
- **WHEN** se trocea un archivo cuyos bloques H1 llevan los bloques de id `BC005_k` y `BC005`
- **THEN** los chunks del primer bloque llevan `document_id` `BC005_k`
- **AND** los del segundo llevan `document_id` `BC005`

#### Scenario: Bloque contenedor sin id propio
- **WHEN** un bloque H1 no tiene bloque de id mientras otros bloques del mismo archivo sí lo tienen,
  como el bloque `Función general` / `Información técnica` de `bc005.md`
- **THEN** se atribuye al código a nivel de archivo y se marca como contenedor
- **AND** su contenido NO se reparte entre las transacciones hijas

### Requirement: El código de transacción autoritativo DEBE salir del contenido del documento
El código aparece dentro del texto (`` `**(BC005_k)**` ``). El nombre de
archivo DEBE ser solo un fallback. Confiar en el nombre de archivo desatribuye
todo archivo multi-transacción, y el corpus muestra nombres que llevan un
prefijo de módulo en vez del código desnudo (`accounting_cpl500` documenta
`CPL500`).

#### Scenario: Código presente en el contenido
- **WHEN** un bloque H1 lleva un bloque de id
- **THEN** se usa ese código, sin importar el nombre de archivo

#### Scenario: Sin código en ninguna parte del documento
- **WHEN** no se encuentra ningún bloque de id en ningún bloque
- **THEN** se usa el stem del nombre de archivo, en mayúsculas, como fallback

### Requirement: Un documento índice DEBE marcarse como tal, sin descartar sus chunks
Un documento capítulo/índice describe un nodo padre y solo enlaza a sus
hijos, sin `Campos` ni `Validaciones` propios — verificado en
`policies/ca001a.md` (31 enlaces, sin secciones de tabla). Trocearlo como
contenido produce chunks de bajo valor que compiten con contenido real en el
retrieval, mientras descartarlo tiraría la única evidencia padre-hijo presente
en el corpus markdown.

Un índice DEBE marcarse con `document_kind` `index` y sus chunks DEBEN
producirse igual. Los dos errores posibles no son simétricos: marcar un índice
real como contenido solo deja algunos chunks de bajo valor, mientras marcar
contenido real como índice sacaría reglas de negocio del camino en silencio.
Marcar en vez de descartar deja la decisión en la capa de retrieval, y respeta
la regla de nunca perder información de negocio sin avisar.

La clasificación DEBE exigir AMBAS condiciones: ausencia de cualquier sección
de tabla pura Y alta densidad de enlaces a otros documentos; cualquier señal
sola produce falsos positivos. Los umbrales están calibrados contra el corpus
(`INDEX_DOC_MIN_LINKS`, `INDEX_DOC_MIN_LINK_DENSITY`) y son settings, no
constantes, porque son elegidos y no derivados.

#### Scenario: Documento capítulo
- **WHEN** se trocea un documento sin sección de tabla pura y con densidad alta
  de enlaces a otros documentos
- **THEN** se reporta con `document_kind` `index`
- **AND** sus chunks se producen igual, cada uno marcado `index` en su metadata
- **AND** sus enlaces quedan expuestos en `child_links` como relaciones padre-hijo

#### Scenario: Documento con sección de tabla, por muchos enlaces que tenga
- **WHEN** un documento tiene una sección de tabla pura y además muchos enlaces
- **THEN** se trata como contenido, porque una señal sola no alcanza

#### Scenario: Documento de contenido con pocos enlaces
- **WHEN** un documento no tiene sección de tabla pero pocos enlaces, o los
  tiene en baja densidad sobre mucha prosa
- **THEN** se trata como contenido, no como índice

### Requirement: La metadata del chunk DEBE llevar el tipo de transacción y el breadcrumb de navegación
El retrieval no puede filtrar hoy por módulo ni por tipo de transacción
porque la metadata no los lleva. Los campos del breadcrumb DEBEN ser planos
en vez de anidados, ya que el vector store filtra por igualdad; y `submodule_*`
DEBE ser opcional, porque la profundidad del árbol varía de verdad.

#### Scenario: Metadata en una transacción clasificada
- **WHEN** se produce un chunk para una transacción cuyo tipo y camino se resuelven
- **THEN** su metadata lleva `transaction_type`, `module_code` y `module_name`
- **AND** `submodule_code` / `submodule_name` cuando el camino tiene ese nivel

#### Scenario: Cada transacción de un archivo multi-transacción lleva su propio tipo
- **WHEN** un archivo describe una transacción y su acompañante `_k`
- **THEN** los chunks de la principal llevan su tipo (p. ej. `functional_abm`)
- **AND** los del acompañante llevan `key_request`

#### Scenario: Metadata cuando la taxonomía no se puede resolver
- **WHEN** el tipo es `unknown` o el breadcrumb queda sin resolver
- **THEN** esos campos están ausentes o explícitamente como unknown
- **AND** no se fabrica ningún valor para rellenarlos

## MODIFIED Requirements

### Requirement: El id y título del documento DEBEN extraerse con tolerancia
El id aparece cerca del título en formatos inconsistentes (`` `(CA014)` ``,
`` `**(CA001k)**` ``) y DEBE leerse con un regex tolerante a markup en negrita
y sufijo en minúscula. La búsqueda DEBE limitarse al texto previo al primer
H2 **del bloque H1 que se está atribuyendo**, no del archivo entero, para que
un documento multi-transacción resuelva un id por bloque en vez de caer al
nombre de archivo para todos.

Limitar la búsqueda a la cabecera de ese bloque sigue evitando que una
referencia a otro documento más abajo en el texto se confunda con el id del
bloque.

#### Scenario: Id en la cabecera de un bloque
- **WHEN** el texto previo al primer H2 de un bloque H1 lleva `` `(CA014)` `` o `` `**(CA001k)**` ``
- **THEN** el `document_id` de ese bloque es `CA014` / `CA001k` respectivamente

#### Scenario: Bloque de id precedido por un H2 en el mismo archivo
- **WHEN** un archivo abre con `## Función general` antes de cualquier bloque de id, como hace `bc005.md`
- **THEN** los bloques H1 posteriores siguen resolviendo sus propios ids
- **AND** el archivo no cae al nombre de archivo para cada chunk

#### Scenario: Sin id encontrado en un bloque
- **WHEN** un bloque H1 no lleva bloque de id
- **THEN** se atribuye según la regla de contenedor, o cae al stem del nombre de archivo
  cuando ningún bloque del archivo lleva id

#### Scenario: Documento sin heading H1
- **WHEN** un documento no tiene heading `# `, como CA014
- **THEN** todo el documento se trata como un solo bloque
- **AND** el título cae a la primera línea no vacía, sin énfasis

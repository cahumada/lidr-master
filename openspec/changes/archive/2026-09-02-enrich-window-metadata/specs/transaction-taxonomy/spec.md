# transaction-taxonomy Delta Specification

## ADDED Requirements

### Requirement: is_menu_node DEBE salir del dato declarado, no de una heurística
El export de `WINDOWS` trae `NWINDOWTY`, y el tipo 8 **es** "Menú". La regla
nodo-vs-hoja se venía derivando de "algo cuelga de este código", que acierta el
97% y falla en 21 códigos [VERIFICADO-CORPUS]: 16 menús vacíos que se
clasificaban como transacciones ejecutables y 5 transacciones con hijos que se
clasificaban como carpetas.

`classify_transaction_type` usa `is_menu_node` para decidir el tipo, así que esos
21 arrastraban el error.

La heurística queda como respaldo, solo para los códigos que el export no trae.

#### Scenario: Menú sin hijos
- **WHEN** un código es de tipo de ventana 8 y nada cuelga de él
- **THEN** `is_menu_node` es verdadero

#### Scenario: Transacción con hijos
- **WHEN** un código tiene hijos y su tipo de ventana no es 8
- **THEN** `is_menu_node` es falso

#### Scenario: Código sin tipo declarado
- **WHEN** el export no trae tipo de ventana para un código
- **THEN** se cae a la heurística de hijos

### Requirement: El tipo de ventana DEBE viajar en la metadata del chunk
El tipo dice cómo se opera una transacción: puntual, secuencia o masiva, y con o
sin encabezado. Es un dato del dominio que no se deduce del texto del documento,
y es lo que hace que *"las transacciones masivas con encabezado"* sea un filtro y
no una lectura manual.

El nombre viaja resuelto y no el código: `6` no le dice nada a nadie,
`Masivo con encabezado` sí, y el chunk se embebe para que lo lea un modelo.

#### Scenario: Tipo estampado
- **WHEN** se produce un chunk de un documento cuyo código está en el export
- **THEN** su metadata lleva el nombre del tipo de ventana

#### Scenario: Sin tipo declarado
- **WHEN** el código no está en el export o no tiene tipo
- **THEN** el campo queda ausente, nunca adivinado

#### Scenario: Filtrable
- **WHEN** se busca restringiendo por tipo de ventana
- **THEN** solo vuelven chunks de transacciones de ese tipo

### Requirement: El rol del sufijo _k DEBE quedar documentado como dominio
`_k` marca la **transacción de encabezado**: el punto de acceso a una
funcionalidad. No es "una solicitud de clave", que es la etiqueta que usan los
documentos, sino un rol en la arquitectura de la aplicación legacy.

De las 52 ventanas `_k` del export, 45 son de tipo "con encabezado"
[VERIFICADO-CORPUS]. Eso explica que `CA001k` tenga 682 chunks y `CA001A` —cuyo
título es "Tratamiento de pólizas"— solo 4: el punto de acceso es el que lleva la
descripción funcional completa, y no es una atribución equivocada del chunker.

El nombre del tipo de transacción `key_request` **no cambia**: es la etiqueta de
los documentos y cambiarla rompería la trazabilidad. Lo que se agrega es el tipo
de ventana al lado.

#### Scenario: La clasificación no cambia
- **WHEN** se clasifica un código con sufijo `_k`
- **THEN** su `transaction_type` sigue siendo `key_request`

#### Scenario: El dominio queda escrito
- **WHEN** alguien lee la documentación del dominio
- **THEN** encuentra qué es una transacción de encabezado y el mapa de los tipos

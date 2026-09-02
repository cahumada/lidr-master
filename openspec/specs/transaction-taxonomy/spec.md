# transaction-taxonomy Specification

## Purpose
Clasificar un código de transacción de VisualTIME por tipo y ubicarlo en el
árbol de navegación Módulo → Submódulo → Transacción, distinguiendo un nodo
de menú de una transacción ejecutable. Implementado en
`app/generation/rag/taxonomy.py` (reglas de nomenclatura, sin I/O) y
`app/generation/rag/navigation.py` (el árbol, cargado de un export de la
tabla `WINDOWS`).

## Requirements

### Requirement: Un código de transacción DEBE clasificarse en un tipo conocido o explícitamente unknown
La clasificación sigue la convención de nombres registrada en
`openspec/domain/visualtime-navigation-taxonomy.md` §4. Esa convención es
conocimiento tácito — no está documentada en ninguna tabla — así que las
reglas DEBEN vivir como datos ordenados (patrón, tipo) en vez de ramas de
código, y DEBEN ser auditables y editables cuando aparezca un contraejemplo.

Un código que no matchea ninguna regla DEBE reportarse como `unknown` con la
razón. Tomar un tipo por defecto propagaría un hecho inventado como si fuera
evidencia.

#### Scenario: Código de interfaz
- **WHEN** se clasifica un código que matchea `INT<digits>`
- **THEN** el tipo es `interface`

#### Scenario: Código de proceso o reporte
- **WHEN** se clasifica un código que matchea `<module>L<digits>`, p. ej. `CAL508`
- **THEN** el tipo es `process_report`

#### Scenario: Código de consulta
- **WHEN** se clasifica un código que matchea `<module>C<digits>`, p. ej. `CAC020`
- **THEN** el tipo es `query`

#### Scenario: Código funcional / ABM
- **WHEN** se clasifica un código sin `L` ni `C` en la posición de módulo, p. ej. `CA001`
- **THEN** el tipo es `functional_abm`

#### Scenario: Código de solicitud de clave
- **WHEN** se clasifica un código con sufijo `_k` / `_K`, p. ej. `BC005_k`, o el
  único caso de `k` pegado, `CA001k`
- **THEN** el tipo es `key_request`
- **AND** el tipo de su familia queda alcanzable por `parent_transaction_code`,
  sin re-derivarlo acá

#### Scenario: Código no reconocido
- **WHEN** un código no matchea ninguna regla
- **THEN** el tipo es `unknown`
- **AND** se reporta la razón en vez de reemplazarla silenciosamente por un default

#### Scenario: El orden de las reglas separa lo específico de lo genérico
- **WHEN** se clasifica un código que matchea tanto un patrón específico como el
  genérico de `functional_abm`, p. ej. `MA0001`, `AGL001`, `AGC001`, `INT54050`
- **THEN** gana el patrón específico, porque las reglas se recorren en orden

### Requirement: El hecho estructural DEBE pisar el patrón del código
Cuando el árbol de `WINDOWS` está disponible, saber que un código tiene hijos
DEBE ganarle a cualquier patrón de nomenclatura: un código con hijos es carpeta
de menú, sea cual sea su forma. `MA6835` es el caso que lo prueba —
indistinguible por patrón de las 941 hojas de mantenimiento, y en realidad una
carpeta. La inferencia por patrón mide 941/942 de acierto, así que la regla
estructural es la que corrige ese 1.

Sin árbol cargado, los patrones deciden solos y esa precisión medida es el
límite conocido.

#### Scenario: Código con hijos, cualquiera sea su patrón
- **WHEN** se clasifica un código cuyo `is_menu_node` es `True`, p. ej. `MA6835`
- **THEN** el tipo es `menu_node`
- **AND** NO el que le habría dado su patrón (`maintenance`)

#### Scenario: Hoja conserva el tipo de su patrón
- **WHEN** se clasifica un código cuyo `is_menu_node` es `False`, p. ej. `MA0001`
- **THEN** el tipo es el de su patrón, `maintenance`

#### Scenario: Sin árbol disponible
- **WHEN** se clasifica un código y no hay dato de `is_menu_node`
- **THEN** deciden los patrones de código solos

### Requirement: Un nodo de menú DEBE distinguirse de una transacción ejecutable estructuralmente
La distinción DEBE salir del árbol en `WINDOWS`, no del patrón visual del
código: un código que aparece como `SCODMEN` de otra fila tiene hijos y es
nodo de menú o carpeta; una hoja que nadie referencia como padre es una
transacción ejecutable. Esta regla es estructural y universal, mientras que
adivinar por la forma del código no lo es — 9 de 11 códigos `M...` probados
resultaron ser carpetas de menú.

#### Scenario: Código con hijos
- **WHEN** un código aparece como `SCODMEN` de al menos otra fila
- **THEN** se clasifica como nodo de menú, no como transacción ejecutable

#### Scenario: Código hoja
- **WHEN** ninguna fila referencia el código como padre
- **THEN** se clasifica como transacción ejecutable

### Requirement: El tipo maintenance DEBE exigir dígitos en el código
`M<módulo><código>` significa mantenimiento. La nota de dominio advierte que un
código `M` puede ser hoja de mantenimiento o carpeta de menú y que solo
`WINDOWS` lo resuelve; medir el corpus mostró que la ambigüedad **no aplica a
los códigos con dígitos**. Las carpetas de menú que la nota cita (`MCONTA`,
`MERCP`, `MCAJBA`, `MGENER`) no llevan dígitos, y ningún código `M` sin dígitos
tiene documento de especificación funcional — `MENU` es el único, y no matchea
la regla. Los 669 códigos `M<letras><dígitos>` del corpus vienen de documentos
que describen una transacción, lo que ya es evidencia de hoja: las carpetas no
tienen documento con Función/Campos/Validaciones.

La regla exige entonces dígitos, y la confirmación por `WINDOWS` sigue siendo
la autoritativa (pendiente, grupo 3 del cambio).

#### Scenario: Código con patrón M y dígitos
- **WHEN** se clasifica un código que matchea `M<letras><dígitos>`, p. ej. `MCO511` o `MA0001`
- **THEN** el tipo es `maintenance`

#### Scenario: Código M sin dígitos
- **WHEN** se clasifica un código `M` sin dígitos, p. ej. `MENU`
- **THEN** NO se clasifica como `maintenance`
- **AND** el tipo es `unknown` con su razón

### Requirement: El árbol DEBE ser opcional
El export de `WINDOWS` es una foto parcial de una instalación, no una
precondición para trocear. Sin el archivo el pipeline DEBE correr igual y
simplemente no resolver breadcrumb.

#### Scenario: Sin archivo de export
- **WHEN** la ruta configurada del export no existe
- **THEN** el chunker produce los mismos chunks que produciría con árbol
- **AND** todo campo de breadcrumb queda en `None`
- **AND** no se lanza ningún error

### Requirement: El recorrido del árbol DEBE tolerar ciclos
El export contiene 2 ciclos. Un recorrido ingenuo colgaría la corrida batch
completa, así que la resolución del camino DEBE llevar guarda de visitados.

#### Scenario: Código dentro de un ciclo
- **WHEN** se resuelve el camino de un código cuya cadena de padres cicla
- **THEN** la resolución termina en vez de colgarse

### Requirement: El breadcrumb de navegación DEBE soportar profundidad variable
El camino desde una transacción hasta la raíz `MENU` DEBE resolverse desde
`WINDOWS`, y su profundidad varía: `CA001` está a dos niveles (módulo, sin
submódulo) mientras `CAC020` está a tres (módulo y luego submódulo). En el
export real la profundidad llega a **6 niveles**, así que el submódulo DEBE ser
el primer nivel bajo el módulo y el camino completo DEBE conservarse para no
perder los intermedios más profundos. Nada DEBE asumir que existe un submódulo,
ni que aplica un conteo fijo de niveles.

#### Scenario: Camino de dos niveles
- **WHEN** se resuelve `CA001`, cuyo camino es `MENU` → `DMECAR` → `CA001`
- **THEN** el módulo es `DMECAR` ("Pólizas")
- **AND** el submódulo está ausente en vez de tomarse por default o fabricarse

#### Scenario: Camino de tres niveles
- **WHEN** se resuelve `CAC020`, cuyo camino es `MENU` → `DMECAR` → `DMECCA` → `CAC020`
- **THEN** el módulo es `DMECAR` ("Pólizas") y el submódulo es `DMECCA` ("Consultas de Pólizas")

#### Scenario: Camino más profundo que los dos casos documentados
- **WHEN** se resuelve un código cuyo camino tiene niveles intermedios de más,
  p. ej. `MA0001` en `MENU > DMEMAN > MTCAR > MPRCO2 > MA0001`
- **THEN** el módulo es el primer nivel bajo la raíz (`DMEMAN`) y el submódulo
  el siguiente (`MTCAR`)
- **AND** el camino completo se conserva, para no perder los niveles restantes

#### Scenario: Código ausente del árbol
- **WHEN** un código no tiene fila en `WINDOWS`
- **THEN** el breadcrumb se reporta como sin resolver en vez de adivinarse parcialmente
- **AND** tampoco se afirma si es nodo u hoja

#### Scenario: Código cuya cadena no llega a la raíz
- **WHEN** un código está en el árbol pero su cadena de padres no llega a `MENU`
  — 794 códigos del export están así
- **THEN** el breadcrumb queda sin resolver, en vez de llamar "módulo" a un
  ancestro cualquiera
- **AND** el hecho de nodo u hoja SÍ se afirma, porque ese sí se conoce

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

# transaction-taxonomy Delta Specification

## ADDED Requirements

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

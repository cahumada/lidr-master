# Tareas de implementación

## 1. El export

- [x] 1.1 `import_windows_tree.py` trae `NWINDOWTY` y `SSHORT_DES`; el CSV pasa
      a 5 columnas.
- [x] 1.2 Lectura compatible hacia atrás: un CSV de 3 columnas sigue cargando y
      deja el tipo sin resolver.
- [x] 1.3 Reimportar el export real y verificar los 11 tipos.

## 2. El árbol

- [x] 2.1 `NavigationTree` guarda `window_type` y expone `window_type_name`.
- [x] 2.2 El mapa código→nombre de los 11 tipos, tomado de `MA0088`.
- [x] 2.3 `is_menu_node` sale de `NWINDOWTY = 8` cuando está, y de la heurística
      de hijos cuando no.
- [x] 2.4 Tests: los 16 menús sin hijos se clasifican como nodo; los 5 con hijos
      que no son de tipo Menú, como transacción.

## 3. El chunk

- [x] 3.1 `window_type_name` en `ChunkMetadata` y estampado en cada chunk.
- [x] 3.2 Columna en `chunks`, migración e índice.
- [x] 3.3 `SearchFilters` acepta `window_type_name`.

## 4. Dominio

- [x] 4.1 `openspec/domain/visualtime-window-types.md`: qué es una transacción
      de encabezado, el mapa de los 11 tipos, y que `_k` no es "solicitud de
      clave" sino un rol.

## 5. Corrida y cierre

- [x] 5.1 Regenerar el corpus y medir cuántos chunks ganan tipo de ventana.
- [x] 5.2 Re-embeber incremental y recargar.
- [x] 5.3 Medir cuántas transacciones cambian de `is_menu_node`.
- [x] 5.4 `pytest`, `pytest -m integration`, `ruff` y `validate_specs` en verde.
- [x] 5.5 Promover el delta y archivar.


## Resultados medidos

| | |
|---|---:|
| Filas del export con tipo declarado | 3.387 de 3.389 |
| Chunks que ganan tipo de ventana | **46.613 de 62.228 (74,9%)** |
| Documentos con tipo | 1.521 de 2.213 (68,7%) |
| Filas en Postgres con tipo | 42.938 de 57.101 |
| Re-embedding | **0 llamadas** |

El re-embedding es cero y tiene que serlo: el tipo de ventana es metadata y no va
en el texto, así que ningún `content_hash` cambia. Que la medición lo confirme es
la prueba de que el hash cubre exactamente los bytes que se embeben.

## `MA6835` no era una carpeta: era un self-loop

La nota `visualtime-navigation-taxonomy.md` registraba `MA6835` como *"carpeta de
menú indistinguible por patrón"* y lo presentaba como **el contraejemplo que
justificaba cargar el árbol**. Un test lo afirmaba.

Es un defecto de datos: esa fila **es su propio padre** —uno de los dos ciclos
que el mapa de procesos ya detectaba— así que el único "hijo" que tiene es él
mismo. La heurística lo contó como padre y lo llamó carpeta. Su tipo declarado es
10, "Tabla general", y su descripción es *"Existencia de Componente para Imprimir
una Cláusula"*.

`has_children` ahora excluye los self-loops, que es la causa raíz. El tipo
declarado confirma el resultado de forma independiente.

Una nota de dominio registró un artefacto como un hecho, y un test lo fijó. Es
exactamente para lo que sirve un campo autoritativo.

## `MEGAA` no es una hoja

La misma nota lo llamaba "transacción real de mantenimiento" porque nada cuelga
de él. El export lo **declara** tipo 8, "Menú": es un menú vacío, y hay 16 así.

Una declaración le gana a una inferencia sacada de la ausencia. Y
`classify_transaction_type` lee `is_menu_node`, así que los 16 se propagaban.

Los dos casos estaban en la nota que el dueño del repo aportó al principio del
proyecto; ninguno de los dos era su error, los dos son artefactos de la
heurística que yo elegí para implementar su regla.

## Un hueco del cargador que este cambio destapó

`ON CONFLICT DO NOTHING` hacía la carga idempotente en contenido y **ciega a la
metadata**. Agregar `window_type_name` a 46.613 chunks con ella no habría
insertado nada y habría dejado la columna en null: el `content_hash` no cambia,
así que cada fila es un conflicto.

Ahora hace `DO UPDATE` sobre las columnas de metadata, y **no** sobre el
embedding: el vector está atado al texto, y si el texto cambió entonces cambió el
hash y es una fila nueva, no un conflicto.

Dos cosas que eso obligó a arreglar:

- **`DISTINCT ON` es necesario, no cosmético.** `DO UPDATE` se niega a afectar la
  misma fila destino dos veces en un comando, y la staging tiene 5.127 hashes
  duplicados — un texto repetido es un hash repetido por construcción.
  `DO NOTHING` lo toleraba en silencio; `DO UPDATE` levanta
  `CardinalityViolation`.
- **`inserted` pasó a llamarse `written`.** El `rowcount` cuenta inserts Y
  updates. Seguir llamándolo "insertadas" habría hecho que una corrida que
  refresca 57.101 filas se leyera como una que insertó 57.101 filas nuevas.

## Lo que NO se cambió, a propósito

`transaction_type = key_request` se queda. Es la etiqueta que usan los documentos
—"solicitud de clave"— y cambiarla rompería la trazabilidad. Lo que se agrega es
el tipo de ventana al lado, que es el dato que explica el patrón.

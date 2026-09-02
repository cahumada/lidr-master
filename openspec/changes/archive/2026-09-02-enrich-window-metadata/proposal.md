## Why

El dueño del repo aclaró qué significa el sufijo `_k`, y la aclaración destapó
que el pipeline está tirando información que ya tiene a mano.

**Lo que significa `_k`:** es la **transacción de encabezado**, el punto de
acceso a esa funcionalidad. No es "una solicitud de clave" —que es la etiqueta
que usan los documentos— sino un rol en la arquitectura de la aplicación legacy.
Y cuál es su patrón depende de cómo esté configurado el tipo de ventana:
secuencia, puntual, masiva, y cada uno con o sin encabezado.

Verificado sobre el export: de las 52 ventanas cuyo código termina en `k`, **45
son de tipo "con encabezado"** [VERIFICADO-CORPUS]:

| tipo | nombre | ventanas `_k` |
|---|---|---:|
| 2 | Secuencia con encabezado | 34 |
| 6 | Masivo con encabezado | 6 |
| 1 | Puntual con encabezado | 5 |

Eso además explica un caso que quedó sin resolver al armar el golden set:
`CA001k` tiene **682 chunks** y `CA001A` —titulado "Tratamiento de pólizas"—
solo 4. Parecía una atribución equivocada del chunker. No lo es: `CA001k` **es**
el punto de acceso, y por eso lleva la descripción funcional completa.

## El pipeline descarta 20 de las 23 columnas del export

`import_windows_tree.py` toma tres columnas: `SCODISPL`, `SCODMEN`,
`SDESCRIPT`. Entre las que descarta está **`NWINDOWTY`**, que es exactamente el
tipo de ventana.

Y `MA0088` —un documento del propio corpus— es la tabla que lo traduce:

| código | tipo de ventana | ventanas |
|---:|---|---:|
| 10 | Tabla general | 605 |
| 5 | Puntual sin encabezado | 522 |
| 2 | Secuencia con encabezado | 458 |
| 3 | Masiva sin encabezado | 383 |
| 6 | Masivo con encabezado | 370 |
| 1 | Puntual con encabezado | 356 |
| 7 | Carpeta específica | 230 |
| 8 | **Menú** | 205 |
| 9 | Carpeta masiva | 183 |
| 11 | Ventana emergente | 68 |
| 4 | Secuencia sin encabezado | 7 |

## El tipo 8 es autoritativo, y mi heurística no

La regla nodo-vs-hoja se implementó por heurística: un código es nodo de menú si
algo cuelga de él. El tipo 8 lo **declara**. Contrastados
[VERIFICADO-CORPUS]:

| | |
|---|---:|
| heurística (tiene hijos) | 194 |
| autoritativo (`NWINDOWTY = 8`) | 205 |
| coinciden | **189** |
| tienen hijos y NO son de tipo Menú | 5 |
| son de tipo Menú y NO tienen hijos | **16** |

97% de acierto, y **21 códigos mal clasificados**. Los 16 menús vacíos son el
error que importa: hoy se clasifican como transacciones ejecutables cuando son
carpetas, y `classify_transaction_type` usa `is_menu_node` para decidir el tipo.

Una heurística que acierta el 97% cuando hay un campo que lo declara es una
heurística que sobra.

## What Changes

- **`import_windows_tree.py`** trae también `NWINDOWTY` y `SSHORT_DES`. El CSV
  pasa de 3 a 5 columnas, con lectura compatible hacia atrás: un CSV viejo de 3
  columnas sigue funcionando, dejando el tipo sin resolver.
- **`navigation.py`** expone `window_type` y `window_type_name`, y usa
  `NWINDOWTY = 8` como fuente autoritativa de `is_menu_node`, con la heurística
  de hijos solo como respaldo para los códigos que el export no trae.
- **`ChunkMetadata`** gana `window_type_name`, y la tabla `chunks` la columna
  correspondiente: "las transacciones masivas con encabezado" pasa a ser un
  filtro y no una lectura.
- **`openspec/domain/`** documenta qué es una transacción de encabezado y el
  mapa de los 11 tipos, porque es conocimiento del dominio que no se deduce del
  corpus.

## Capabilities

### Capability modificada

- `transaction-taxonomy`: el tipo de ventana como dato declarado, y el rol de
  encabezado del sufijo `_k`.

## Impact

- `scripts/import_windows_tree.py`, `app/generation/rag/navigation.py`.
- `app/generation/rag/schemas.py`, `app/generation/rag/chunking/functional_spec.py`.
- `app/generation/rag/store/models.py` + una migración.
- `openspec/domain/visualtime-window-types.md` — nuevo.
- Regenerar el corpus, re-embeber incremental y recargar.

## Lo que este cambio NO hace

- **No reclasifica `key_request`.** El nombre del tipo de transacción se queda:
  es la etiqueta que usan los documentos y cambiarlo rompería la trazabilidad.
  Lo que se agrega es el tipo de ventana al lado, que es el dato que explica el
  patrón.
- **No importa `NMODULES`.** Son 99 códigos numéricos que necesitan su propia
  tabla de traducción, que no está identificada. Habría que resolver eso antes,
  y el módulo del corpus ya cubre la agrupación que hacía falta.
- **No toca el mapa de procesos.** El tipo de ventana enriquece el nodo, no
  agrega aristas.

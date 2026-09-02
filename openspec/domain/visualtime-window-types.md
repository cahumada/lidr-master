# Tipos de ventana y transacciones de encabezado

Conocimiento del dominio aportado por el dueño del repo, verificado contra el
export de `WINDOWS` y contra `MA0088` del propio corpus. No se deduce del texto
de los documentos.

## El sufijo `_k` es un rol, no una etiqueta

Un código que termina en `_k` (o `k`) es la **transacción de encabezado**: el
**punto de acceso** a esa funcionalidad en la arquitectura de la aplicación
legacy.

Los documentos la llaman *"solicitud de clave"*, y de ahí sale el
`transaction_type = key_request` del pipeline. **Ese nombre se queda** —es la
etiqueta de los documentos y cambiarlo rompería la trazabilidad— pero describe
la pantalla, no el rol.

Cuál es el patrón de esa transacción lo determina su **tipo de ventana**.
Verificado: de las 52 ventanas `_k` del export, **45 son de tipo "con
encabezado"** [VERIFICADO-CORPUS]:

| tipo | nombre | ventanas `_k` |
|---:|---|---:|
| 2 | Secuencia con encabezado | 34 |
| 6 | Masivo con encabezado | 6 |
| 1 | Puntual con encabezado | 5 |
| otros | | 7 |

### Lo que esto explica

`CA001k` tiene **682 chunks** y `CA001A` —titulado "Tratamiento de pólizas"—
solo **4**. Parecía una atribución equivocada del chunker.

No lo es: `CA001k` **es** el punto de acceso al tratamiento de pólizas, y por eso
lleva la descripción funcional completa. El archivo `ca001.md` declara un solo id
en su línea 3, `CA001k`, y **`CA001` no está declarado como id en ningún archivo
del corpus**: el nombre del archivo y el id de la transacción no coinciden en el
export.

Consecuencia práctica para anotar: una referencia a `ca001.md` se anota como
`CA001k`.

## Los 11 tipos de ventana

De `MA0088` ("Tipo de ventana"), tabla interna número 88, de valores fijos. La
columna `NWINDOWTY` del export de `WINDOWS` lleva el código.

| código | nombre | ventanas |
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

3.387 de las 3.389 filas del export declaran un tipo.

El pipeline estampa el **nombre** y no el código en `metadata.window_type_name`:
`6` no le dice nada a nadie y el chunk se embebe para que lo lea un modelo.

## El tipo 8 reemplaza a una heurística, y corrige un artefacto

La regla nodo-vs-hoja se venía derivando de *"algo cuelga de este código"*. El
tipo 8 lo **declara**. Contrastados [VERIFICADO-CORPUS]:

| | |
|---|---:|
| heurística (tiene hijos) | 192 |
| autoritativo (`NWINDOWTY = 8`) | 205 |
| difieren | **19** |

Los 16 **menús vacíos** son el error que importaba: se clasificaban como
transacciones ejecutables cuando son carpetas, y `classify_transaction_type` lee
`is_menu_node`, así que el error se propagaba. `MEGAA` ("Generación de asientos
automáticos") es uno de ellos.

La heurística queda como respaldo, solo para los códigos que el export no trae.

### `MA6835` no era una carpeta: era un self-loop

La nota `visualtime-navigation-taxonomy.md` registraba `MA6835` como *"carpeta de
menú indistinguible por patrón"*, y lo presentaba como el contraejemplo que
justificaba cargar el árbol.

**Es un defecto de datos.** Esa fila es **su propio padre** —uno de los dos ciclos
que detecta el mapa de procesos— así que el único "hijo" que tiene es él mismo.
La heurística lo contó como padre y lo llamó carpeta; su tipo declarado es 10,
"Tabla general", y su descripción es *"Existencia de Componente para Imprimir una
Cláusula"*.

`has_children` ahora excluye los self-loops, que es la causa raíz, y el tipo
declarado confirma el resultado.

Que una nota de dominio haya registrado un artefacto como un hecho es
exactamente para lo que sirve un campo autoritativo.

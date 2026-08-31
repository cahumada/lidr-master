# Decisiones de diseño

## 1. Sidecar binario en lugar de vectores inline

**Alternativa descartada:** agregar `embedding: list[float]` al `Chunk` y
dejarlo en el corpus JSON.

1536 floats serializados como texto son ~30 KB por chunk. Por 61.901 chunks,
~1,8 GB repartidos en 26 archivos JSON. El corpus dejaría de ser algo que se
puede abrir, leer y diffear —que es exactamente para lo que sirve hoy— y cada
lectura del corpus para cualquier otro fin pagaría el parseo de los vectores.

**Elegido:** `data/embeddings/<módulo>.npy` (float32, forma `(n, 1536)`) más
`data/embeddings/<módulo>.index.json` con una entrada por fila. El `.npy` se
mapea a memoria y se lee por fila sin cargar los 380 MB.

**Costo aceptado:** dos archivos que pueden desincronizarse. Se mitiga con el
`content_hash` en el índice: la verificación compara el índice contra el corpus
y falla si no coinciden, en lugar de confiar en que el orden se mantuvo.

## 2. La identidad de una fila es su `content_hash`, no su posición

Guardar solo "la fila 4021 es el chunk 4021 de policies.json" hace que
cualquier cambio en el corpus —un documento nuevo, un chunk que desaparece—
corra todos los índices y los vectores queden apuntando a otro texto, en
silencio.

El índice guarda `(tenant_id, doc_version, chunk_id, content_hash)` por fila.
La reingesta incremental entonces es una operación de conjuntos:

- hash en el índice y en el corpus → **reutilizar** el vector
- hash solo en el corpus → **embeber**
- hash solo en el índice → **descartar** la fila (su chunk ya no existe)

No hace falta que el orden se conserve entre corridas.

## 3. Reanudación: por módulo, con checkpoint dentro del módulo

**Descartado:** un solo `.npy` para todo el corpus. 380 MB que hay que reescribir
entero ante cualquier cambio, y que no se puede escribir de a partes.

**Elegido:** un archivo por módulo (26 archivos, el más grande ~120 MB) y,
dentro de un módulo, se persiste cada N lotes. Un corte deja el módulo
parcialmente embebido y la corrida siguiente retoma desde el primer hash que
falta.

El módulo es la unidad natural porque ya lo es en el corpus: `policies.json`,
`accounting.json`. Alinear las particiones evita un mapeo más entre artefactos.

## 4. Reintentos: backoff exponencial sobre errores transitorios, y nada más

Un `429` o un `500` se reintentan; un `400` (input inválido) o un `401` (clave
mala) no —reintentarlos solo demora el diagnóstico. El lote que agota los
reintentos **no aborta la corrida**: se registra como fallido, se sigue con el
resto, y al final se reporta la lista. Un módulo entero perdido porque un lote
tuvo mala suerte es peor que un corpus 99,8% embebido y un reporte que dice qué
falta.

Esa lista de fallidos es reanudable por el mismo mecanismo del punto 2: sus
hashes simplemente no están en el índice.

## 5. Verificación antes y después

**Antes de la primera llamada** (barato, evita gastar de más):

- ningún chunk excede el límite de tokens del modelo
- ningún `text` está vacío
- ningún `content_hash` duplicado dentro de un mismo `(tenant, versión)`

**Después de escribir:**

- filas == chunks a embeber
- dimensión == la declarada en `Settings`
- ninguna fila es todo ceros (una API que devuelve un vector nulo es un fallo
  silencioso: el chunk se indexa y nunca aparece en ningún resultado)
- todo hash del índice existe en el corpus

## 6. El embedder es un protocolo, y el de tests es determinístico

`Embedder` es un `Protocol` con un solo método `embed(texts) -> list[list[float]]`.
La implementación de test deriva el vector del hash del texto: mismo texto,
mismo vector, sin red y sin clave. Así la suite verifica el batching, la
reanudación, el mapeo de índices y la verificación —que es donde están los bugs
reales— sin depender de OpenAI.

`OpenAIEmbedder` se prueba contra un doble del cliente, no contra la API.

## 7. Dimensión: 1536, sin recortar

`text-embedding-3-small` soporta `dimensions` reducidas (MRL). No se usa: 380 MB
no es un problema de almacenamiento acá, y recortar la dimensión es una pérdida
de calidad que solo se justifica cuando el índice no entra. Queda como
`EMBEDDING_DIMENSIONS` en `Settings` por si esa condición cambia, y se verifica
contra lo que la API realmente devuelve en lugar de asumirlo.

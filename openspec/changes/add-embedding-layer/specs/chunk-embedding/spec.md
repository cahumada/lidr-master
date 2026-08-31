# chunk-embedding Delta Specification

## ADDED Requirements

### Requirement: El vector de un chunk DEBE cubrir exactamente lo que se hasheó
El `content_hash` de un chunk se calcula sobre su `text` completo, header
contextual incluido. El embedding DEBE generarse sobre ese mismo `text`, sin
recortes ni reescrituras. Si difirieran, el hash dejaría de ser evidencia de que
el vector sigue siendo válido y la reingesta incremental sería incorrecta en
silencio.

#### Scenario: Texto embebido
- **WHEN** se embebe un chunk
- **THEN** el texto enviado al modelo es exactamente `chunk.text`

#### Scenario: Mismo texto, mismo vector
- **WHEN** el mismo texto se embebe dos veces con un embedder determinístico
- **THEN** los dos vectores son idénticos

### Requirement: Los vectores DEBEN persistirse en un sidecar binario junto a un índice
Los vectores NO DEBEN incorporarse al corpus JSON: 1536 floats por chunk lo
llevarían de 76 MB a ~1,8 GB y dejaría de ser auditable a mano.

Cada módulo produce dos artefactos: un `.npy` float32 de forma `(n, dims)` y un
`.index.json` con una entrada por fila que lleva `tenant_id`, `doc_version`,
`chunk_id`, `document_id` y `content_hash`.

#### Scenario: Artefactos por módulo
- **WHEN** termina de embeberse el módulo `policies`
- **THEN** existen `data/embeddings/policies.npy` y `data/embeddings/policies.index.json`
- **AND** el `.npy` tiene tantas filas como entradas el índice

#### Scenario: La fila N del binario corresponde a la entrada N del índice
- **WHEN** se lee la fila `n` del `.npy`
- **THEN** el chunk al que pertenece es el de la entrada `n` del índice

### Requirement: La identidad de una fila DEBE ser su content_hash, no su posición
Un corpus regenerado puede tener chunks nuevos, desplazados o eliminados.
Vincular un vector a su posición haría que esos cambios reapuntaran vectores a
otro texto sin ninguna señal.

#### Scenario: Corpus sin cambios
- **WHEN** se vuelve a correr el batch sobre un corpus cuyos `content_hash` ya
  están todos en el índice
- **THEN** no se hace **ninguna** llamada al modelo
- **AND** los artefactos quedan como estaban

#### Scenario: Un documento cambió
- **WHEN** un corpus regenerado trae hashes nuevos y ya no trae otros
- **THEN** se embeben solo los hashes nuevos
- **AND** las filas cuyo hash ya no está en el corpus se descartan del sidecar

#### Scenario: Chunks reordenados sin cambiar de contenido
- **WHEN** los mismos chunks aparecen en otro orden
- **THEN** no se hace ninguna llamada al modelo

### Requirement: Una corrida interrumpida DEBE poder retomarse
61.901 chunks son cientos de llamadas. Una corrida que hay que empezar de cero
ante cualquier corte no termina nunca.

El progreso SE DEBE persistir dentro de un módulo, no solo al terminarlo.

#### Scenario: Corte a mitad de un módulo
- **WHEN** una corrida se interrumpe después de escribir un checkpoint
- **THEN** la corrida siguiente retoma desde el primer hash que falta
- **AND** no vuelve a embeber lo ya persistido

### Requirement: Un lote fallido NO DEBE abortar la corrida
Se reintenta con backoff exponencial ante errores transitorios (429, 5xx).
Los errores no transitorios (400, 401) NO se reintentan: solo demoran el
diagnóstico.

Agotados los reintentos, el lote se registra como fallido y la corrida
**continúa**. Un corpus 99,8% embebido con un reporte de qué falta es mejor que
una corrida abortada.

#### Scenario: Error transitorio
- **WHEN** una llamada falla con un error reintentable
- **THEN** se reintenta con espera creciente hasta el máximo configurado

#### Scenario: Error no reintentable
- **WHEN** una llamada falla con un error de input o de autenticación
- **THEN** no se reintenta

#### Scenario: Lote que agota los reintentos
- **WHEN** un lote falla definitivamente
- **THEN** la corrida sigue con los lotes restantes
- **AND** el lote fallido aparece en el reporte final
- **AND** el proceso termina con código de salida distinto de cero

### Requirement: El corpus DEBE verificarse antes de la primera llamada
Descubrir un chunk inválido cuando la API lo rechaza es pagar por averiguarlo.
La validación previa es barata y se hace entera antes de gastar.

#### Scenario: Chunk que excede el límite del modelo
- **WHEN** un chunk supera el máximo de tokens de entrada del modelo
- **THEN** la corrida se detiene nombrando el chunk, antes de cualquier llamada

#### Scenario: Chunk vacío
- **WHEN** el `text` de un chunk está vacío o es solo espacios
- **THEN** la corrida se detiene nombrando el chunk

### Requirement: Un content_hash repetido DEBE embeberse una sola vez
Mismo hash es, por construcción, mismo texto: embeberlo dos veces devuelve el
mismo vector y se paga dos veces. En el corpus real hay **5.451 filas repetidas
sobre 61.901 (8,8%)** — un mismo fragmento que aparece muchas veces dentro de un
módulo (`"De lo contrario,"` 72 veces, `"No"` 51 veces).

Por eso la fila del sidecar es el **content_hash único**, no el chunk: el
consumidor une el corpus con los vectores por hash. La entrada del índice
conserva el `chunk_id` y el `document_id` del primer chunk que produjo esa fila,
como referencia de trazabilidad, no como identidad.

#### Scenario: Texto repetido dentro de un módulo
- **WHEN** N chunks de un módulo comparten el mismo `content_hash`
- **THEN** el módulo produce **una** fila para ese hash
- **AND** se hace una sola llamada por ese texto

#### Scenario: El corpus se une a los vectores por hash
- **WHEN** un consumidor busca el vector de un chunk
- **THEN** lo encuentra por su `content_hash`, no por su posición en el corpus

### Requirement: Los vectores escritos DEBEN verificarse
Un vector nulo no falla: el chunk se indexa y no aparece nunca en ningún
resultado. Ese fallo silencioso se detecta al escribir, no en producción.

#### Scenario: Verificación posterior
- **WHEN** termina la corrida
- **THEN** se verifica que la cantidad de filas coincide con la de chunks
- **AND** que la dimensión es la configurada
- **AND** que ninguna fila es todo ceros
- **AND** que todo hash del índice existe en el corpus
- **AND** que ningún hash aparece dos veces en el índice

#### Scenario: Dimensión inesperada del modelo
- **WHEN** el modelo devuelve vectores de una dimensión distinta a la configurada
- **THEN** la corrida falla en lugar de escribir un sidecar inconsistente

### Requirement: DEBE poder estimarse el costo sin gastar
Antes de una corrida de miles de llamadas hay que poder saber cuántas son y
cuánto salen.

#### Scenario: Dry run
- **WHEN** el batch corre con `--dry-run`
- **THEN** informa filas a embeber, filas reutilizadas, duplicados ahorrados,
  tokens, lotes y costo estimado
- **AND** no hace ninguna llamada al modelo

### Requirement: La suite de tests NO DEBE depender de la red ni de una clave
`Embedder` es un protocolo. La implementación de test deriva el vector del hash
del texto: determinística, sin red, sin `OPENAI_API_KEY`. Es lo que permite
testear batching, reanudación, mapeo de índices y verificación —donde están los
bugs reales— en cada corrida.

#### Scenario: Tests sin clave
- **WHEN** se corre la suite sin `OPENAI_API_KEY` en el entorno
- **THEN** todos los tests de esta capability pasan

#### Scenario: El cliente de OpenAI se prueba contra un doble
- **WHEN** se testea `OpenAIEmbedder`
- **THEN** se usa un doble del cliente, nunca la API real

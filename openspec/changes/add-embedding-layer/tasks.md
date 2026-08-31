# Tareas de implementación

## 1. Contrato y configuración

- [x] 1.1 `Embedder` como `Protocol` con `embed(texts) -> list[list[float]]`,
      para que la capa de batch no conozca a OpenAI.
- [x] 1.2 `EmbeddingIndexEntry` y `EmbeddingManifest` en `schemas.py`, con la
      convención bilingüe (`EN || ES`) del resto del proyecto.
- [x] 1.3 `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `EMBEDDING_BATCH_SIZE`,
      `EMBEDDING_MAX_RETRIES`, `EMBEDDING_MAX_INPUT_TOKENS`, `EMBEDDINGS_PATH`
      en `Settings`.
- [x] 1.4 `openai` y `numpy` en `pyproject.toml`.

## 2. Sidecar

- [x] 2.1 Escritura de `<módulo>.npy` (float32) y `<módulo>.index.json`.
- [x] 2.2 Lectura del sidecar existente → conjunto de `content_hash` ya
      embebidos.
- [x] 2.3 Descarte de filas cuyo hash ya no está en el corpus.
- [x] 2.4 Checkpoint dentro de un módulo, no solo al terminarlo.
- [x] 2.5 Test: escribir, releer y recuperar el vector de un `content_hash`.
- [x] 2.6 Test: reordenar los chunks del corpus no genera ninguna llamada.

## 3. Embedder de OpenAI

- [x] 3.1 Batching por `EMBEDDING_BATCH_SIZE`.
- [x] 3.2 Backoff exponencial solo sobre errores transitorios (429, 5xx).
- [x] 3.3 Un lote que agota reintentos se registra y la corrida sigue.
- [x] 3.4 Verificación de la dimensión que devuelve la API contra la
      configurada — falla en vez de escribir un sidecar inconsistente.
- [x] 3.5 Test contra un doble del cliente: batching, reintentos, no-reintento
      de 400/401, lote fallido que no aborta.

## 4. Embedder determinístico para tests

- [x] 4.1 `HashEmbedder`: vector derivado del SHA-256 del texto, normalizado.
- [x] 4.2 Test: la suite completa pasa sin `OPENAI_API_KEY` en el entorno.

## 5. Verificación

- [x] 5.1 Previa: ningún chunk supera el límite de tokens, ningún `text` vacío.
- [x] 5.1b Deduplicar por `content_hash`: 5.451 filas repetidas de 61.901
      (8,8%). La fila del sidecar es el hash único, no el chunk.
- [x] 5.2 Posterior: filas == chunks, dimensión correcta, ninguna fila en cero,
      todo hash del índice presente en el corpus.
- [x] 5.3 Test: un vector nulo devuelto por un embedder falso es detectado.

## 6. Batch

- [x] 6.1 `scripts/embed_corpus.py` recorriendo `data/chunks/*.json`, usando la
      raíz de composición (no instanciando el embedder por su cuenta — es el
      bug que ya nos costó un corpus con 0% de breadcrumb).
- [x] 6.2 `--dry-run`: chunks a embeber, reutilizados, tokens, lotes y costo.
- [x] 6.3 `embeddings_manifest.json` y `embedding_report.md`.
- [x] 6.4 Código de salida distinto de cero si quedaron lotes fallidos.

## 7. Corrida real y cierre

- [x] 7.1 `--dry-run` sobre el corpus completo y contraste con la estimación
      del proposal (61.901 chunks, ~US$ 0,10).
- [ ] 7.2 Corrida real contra OpenAI. **BLOQUEADA**: no hay `OPENAI_API_KEY`.
      En su lugar se corrió el pipeline completo sobre el corpus real con el
      `HashEmbedder` (1536 dims, sin red): 56.480 filas en 28 módulos, **348 MB**,
      0 lotes fallidos, verificación en disco OK. La re-corrida hizo **0**
      llamadas y reutilizó las 56.480 filas en 1,3 s.
- [x] 7.3 Re-corrida inmediata: DEBE hacer cero llamadas.
- [ ] 7.4 Promover el delta a `openspec/specs/chunk-embedding/spec.md` y
      archivar el change.


## Hallazgos de la implementación

- **Deduplicación (no estaba en el proposal).** 5.451 de 61.901 chunks son
  texto repetido; 5.421 dentro de un mismo módulo. La fila del sidecar pasó a
  ser el `content_hash` único: 56.480 filas en vez de 61.901, **8,8% menos**
  de llamadas y de costo. Documentado en la spec.

- **`np.save` con una ruta le agrega su propio `.npy`.** El archivo temporal
  `policies.npy.tmp` aterrizaba como `policies.npy.tmp.npy` y el `replace`
  atómico fallaba. Lo encontraron 20 tests a la vez. Se escribe por handle.

- **Un `→` abortó una corrida completa.** La consola de Windows es cp1252; la
  excepción saltó en el último `print`, después de escribir los 28 sidecars, el
  manifiesto y el reporte. La salida de consola quedó ASCII y hay un test que
  la codifica a cp1252.

- **Números medidos vs. estimados:** 348 MB reales contra los 380 MB del
  proposal (la diferencia es la deduplicación), y US$ 0,0951 contra US$ 0,10.

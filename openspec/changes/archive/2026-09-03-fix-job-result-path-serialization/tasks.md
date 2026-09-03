# Tareas

- [x] 1.1 `ChunkStepResult.summary()`: `out_dir` a `str`.
- [x] 1.2 `LoadStepResult.summary()`: `chunks_dir` a `str`.
- [x] 1.3 `EmbedStepResult.summary()` ya existia; se corrige para tambien
      convertir su `out_dir`, que quedaba pasando de largo.
- [x] 1.4 `ResetStepResult` revisado: no tiene ningun campo `Path`, no necesita
      `summary()`.
- [x] 2.1 Test que fija el defecto: `asdict()` a secas deja un `Path` real y
      `json.dumps` lo rechaza. Sin este test, un `Path` nuevo agregado a
      cualquiera de estas dataclasses puede volver a colarse sin que nada
      avise.
- [x] 2.2 Tests de que las tres `summary()` son JSON-serializables de verdad
      (`json.dumps` sin excepcion), no solo que no tiran error en un caso.
- [x] 2.3 Test de que `EmbedStepResult.summary()` sigue sacando
      `module_results` y `manifest`, que tampoco son serializables.
- [x] 3.1 Verificado contra Railway: el job fallido (`e26c7cdc`) tiene el
      mensaje exacto de este bug; el job posterior al arreglo (`bce89257`)
      quedo `succeeded` con `out_dir`/`chunks_dir` guardados como string.
- [x] 3.2 `pytest` (503) y `ruff check .` en verde.
- [x] 3.3 Promover y archivar.

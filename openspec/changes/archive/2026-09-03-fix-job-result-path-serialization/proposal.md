## Why

Un rebuild real fallo en produccion: `WindowsPath is not JSON serializable`, al
escribir el progreso despues del paso de trocear. `ingestion_jobs.result` es
JSONB, y `ChunkStepResult.out_dir` y `LoadStepResult.chunks_dir` son campos
`Path` de verdad -- se agregaron en el cambio que versiono los artefactos por
version de documentacion, para que el reporte de cada script cayera al lado de
sus artefactos.

`dataclasses.asdict()` no convierte un `Path` a texto, asi que
`report(result=dict(results))` -- llamado despues de CADA paso, no solo al
final -- intentaba escribir un objeto no serializable en cuanto terminaba el
paso de trocear. Se verifico contra la base real de Railway: el job que corrio
antes del arreglo quedo `failed` con exactamente ese mensaje; el que corrio
despues quedo `succeeded` con `out_dir` guardado como string.

## What Changes

`ChunkStepResult` y `LoadStepResult` ganan un `summary()` que convierte su campo
`Path` a `str`, igual que ya tenia `EmbedStepResult` para sus objetos no
serializables (`module_results`, `manifest`). El runner ya llamaba
`outcome.summary() if hasattr(outcome, "summary") else asdict(outcome)`, asi que
agregar el metodo alcanza -- no hizo falta tocar el runner.

Se agregan 4 tests que fijan el defecto y el arreglo: `asdict()` a secas SIGUE
dejando pasar un `Path` (para que quede visible por que existe `summary()`), y
las tres `summary()` son JSON-serializables de verdad, no solo "no tira error en
este caso puntual".

## Impact

- `app/ingestion/pipeline.py`: dos metodos `summary()` nuevos.
- 4 tests en `tests/ingestion/test_pipeline.py`.
- Sin migracion: la tabla ya existia, el bug era de escritura y no de esquema.
- Verificado contra la base real de Railway: 56.938 filas cargadas
  correctamente en la corrida que ya tenia el arreglo.

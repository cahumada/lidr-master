## Why

Los documentos fuente van a vivir en un bucket S3-compatible de Railway, no en
un disco local. Hoy el paso de trocear hace `root.rglob("*.md")` y
`path.read_text()`, y ninguna de las dos cosas existe sobre object storage.

Este es el momento que el repo estaba esperando para una abstracción. La regla
escrita en `openspec/project.md` dice:

> `base.py` existe pero **sin** la clase abstracta `Chunker` del curso: acá hay
> una sola estrategia, y una abstracción con una única implementación es ruido.
> Se agrega cuando entre la segunda estrategia.

**Entró la segunda fuente.** No es especulación: hay un bucket concreto y un
directorio local que tiene que seguir funcionando para la CLI y los tests.

## What Changes

`CorpusSource` como `Protocol`, con la superficie mínima que el chunking
realmente usa —dos métodos, no un sistema de archivos:

| | |
|---|---|
| `modules()` | los documentos agrupados por módulo |
| `read(key)` | el texto de uno |

Dos implementaciones:

- **`LocalCorpusSource`**: lo de hoy, sobre un `Path`. Es lo que usan la CLI y
  los tests, y no necesita red ni credenciales.
- **`S3CorpusSource`**: sobre un bucket S3-compatible, con `endpoint_url`
  configurable —que es lo que lo hace servir para Railway, MinIO o AWS.

El agrupamiento por módulo es el mismo criterio en las dos: el primer segmento
de la ruta relativa. En un bucket eso es el primer segmento de la clave, porque
S3 no tiene directorios: `policies/ca014.md` pertenece a `policies` por su
prefijo y no por estar adentro de nada.

## Impact

- `app/ingestion/source.py` nuevo.
- `chunk_corpus()` recibe una `CorpusSource` en lugar de una `root: Path`.
- `Settings`: `CORPUS_BUCKET`, `CORPUS_BUCKET_PREFIX`, `S3_ENDPOINT_URL`,
  `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`.
- **Una dependencia nueva: `boto3`.** Justificada: el protocolo S3 exige firmar
  cada request con AWS SigV4, y escribir eso a mano es criptografía de
  autenticación hecha en casa — exactamente lo que no hay que hacer. `boto3` es
  el cliente de referencia y habla con cualquier endpoint S3-compatible.

### Lo que este cambio NO resuelve, y hay que decirlo

El pipeline toca disco en **dos** lugares y este cambio arregla uno solo:

| | qué hace | tamaño |
|---|---|---:|
| fuente | leer los markdown | — |
| artefactos | escribir y leer el corpus troceado y el sidecar | **437 MB** |

El corpus generado son 86 MB y el sidecar 351 MB. En un contenedor de Railway sin
volumen, el filesystem es efímero: se pierden en cada deploy.

Medido, eso cuesta menos de lo que parece —re-trocear son 15 s y re-embeber
**US$ 0,10** por 4.751.041 tokens— pero son ~446 lotes contra la API de OpenAI
cada vez que el contenedor arranca de cero.

Y hay un camino mejor que no voy a implementar de apuro, porque tiene un modo de
falla peligroso. El dato: `embedding` está en `COPY_COLUMNS` pero **no** en
`_METADATA_COLUMNS`, así que en un conflicto **nunca se reescribe**. O sea que
para un hash que ya está en Postgres el vector no hace falta: la base ya lo
tiene. El sidecar podría ser una optimización en lugar de un requisito.

Lo que lo hace delicado es que `embedding` es `NOT NULL`: una fila que resulta
ser nueva y llega sin vector real necesitaría un placeholder, y un vector en cero
insertado por error se indexa donde nada matchea nunca — el fallo silencioso que
la capa de embeddings ya rechaza a propósito. Requiere consultar primero qué
hashes existen y tratar distinto los dos casos. Va en su propio cambio.

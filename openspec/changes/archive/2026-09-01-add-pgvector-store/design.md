# Decisiones de diseño

## 1. HNSW y no IVFFlat

IVFFlat necesita entrenarse sobre datos ya cargados y su recall depende de que
`lists` y `probes` estén bien elegidos para el tamaño del corpus; recargar con
otro volumen obliga a reconstruirlo. HNSW no se entrena, no depende del orden de
carga y da mejor recall a la misma latencia. Cuesta más construirlo y ocupa más
memoria, que a 57.131 filas no es un problema.

El operator class del índice **debe** coincidir con el operador de la consulta
(`vector_cosine_ops` con `<=>`). Si no coinciden, Postgres no falla: ignora el
índice y hace scan secuencial. Sería un problema de rendimiento invisible, así
que hay un test que verifica el plan.

Coseno y no producto interno aunque los embeddings de OpenAI vengan
normalizados y el ranking sea equivalente: la normalización es una propiedad del
proveedor, no del esquema, y el día que se cambie de modelo el coseno sigue
estando bien.

## 2. Una tabla `chunks`, con la metadata en columnas y no en JSONB

El curso guarda `metadata_` como JSONB con un índice GIN. Tiene sentido cuando
la metadata es abierta.

La nuestra no lo es: `ChunkMetadata` es un modelo Pydantic con campos fijos, y
son justamente los que se van a filtrar. En columnas se pueden indexar de a
pares, el planner tiene estadísticas reales y un typo en el nombre de un campo
es un error de SQL en lugar de un filtro que no matchea nada.

JSONB queda para lo que no tiene forma, que hoy es nada.

## 3. La identidad de una fila, otra vez, es el `content_hash`

`(tenant_id, doc_version, content_hash)` es la clave única. Ya se decidió en
`chunk-embedding` y por la misma razón: el `chunk_id` es un localizador que se
corre cuando el corpus se regenera, y atar la identidad a la posición hace que
una recarga apunte filas a otro texto sin ninguna señal.

Esto es lo que hace la carga **idempotente**: `ON CONFLICT DO NOTHING` sobre esa
clave. Correrla dos veces no duplica; correrla después de regenerar el corpus
inserta lo nuevo y deja lo que no cambió.

El `chunk_id` se guarda igual, como columna común: es la trazabilidad al
documento fuente.

## 4. Cargar por `COPY`, no por el ORM

57.131 filas de 1536 floats. `session.add_all()` construye 57.131 objetos ORM,
los rastrea en la identity map y emite INSERTs; en la práctica son minutos y
mucha memoria para un trabajo que `COPY` hace de una.

El ORM define el esquema y responde las consultas. Mover el bulto es de
psycopg3.

`COPY` va contra una tabla temporal y después se hace
`INSERT ... SELECT ... ON CONFLICT DO NOTHING`. Copiar directo a la tabla final
no permite `ON CONFLICT`, y la idempotencia vale el paso extra.

## 5. Dos stacks: sync para cargar, async para consultar

Es lo que hace el curso, y la razón se sostiene acá: la carga es un batch
offline donde `COPY` sincrónico es lo más simple y lo más rápido; la consulta va
a estar en el camino de un request HTTP, donde bloquear el event loop por cada
búsqueda no escala.

Ambos salen del mismo `DATABASE_URL`; el stack async le cambia el driver.

No es especulativo: el endpoint de búsqueda es el próximo cambio, y ponerlo
async después obliga a tocar las firmas del repositorio y el cableado.

## 6. Una sola versión activa por cliente, garantizada por la base

`corpus_versions` lleva `(tenant_id, doc_version, status, activated_at)`. Un
índice único parcial sobre `tenant_id WHERE status = 'active'` hace que dos
versiones activas del mismo cliente sean **imposibles**, no improbables.

Una regla así en el código de la aplicación se rompe con dos procesos
concurrentes. En la base no.

La tabla NO tiene foreign key contra `chunks`: una versión puede declararse
antes de terminar de cargarla, y una carga a medias no debería activarse sola.
Activar es explícito.

## 7. Full-text en español, generado por la base

`content_tsv` es una columna generada `STORED`: `to_tsvector('spanish', text)`.
Generada y no calculada al vuelo porque el índice GIN necesita un valor
materializado, y `STORED` garantiza que no puede quedar desincronizada del
texto — no hay trigger que mantener ni carga que pueda olvidarse de poblarla.

`'spanish'` es parte del esquema, no un parámetro: cambiarlo obliga a
reconstruir la columna y el índice, así que queda declarado en la migración y
hay un test que verifica que `pólizas` y `póliza` colapsan al mismo lexema.

Todavía no se usa para buscar —eso es `retrieval`— pero la columna se crea
ahora: agregarla después es reescribir 57.131 filas.

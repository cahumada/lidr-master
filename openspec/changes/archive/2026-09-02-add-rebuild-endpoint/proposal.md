## Why

Hoy el pipeline completo se corre con tres comandos de consola. Eso sirve para
desarrollar y no sirve para operar: apuntar el servicio a otra base
—cambiar `DATABASE_URL`— y después necesitar una terminal y este repo clonado
para poblarla es una dependencia que no debería existir.

El curso resuelve esto con `app/ingestion/`: pipeline batch con jobs en
background y tracking en Postgres. Es la capa que este proyecto no replicó, y la
justificación registrada («ingesta síncrona, sin persistencia») **venció cuando
entró pgvector**.

## What Changes

### Un solo lugar donde vive la orquestación

Hoy está dentro de los `main()` de tres scripts, mezclada con parseo de
argumentos, armado de reportes y `print`. Si el endpoint la reimplementa, hay
dos pipelines que van a divergir — y el que se rompa en silencio va a ser el que
nadie corre a mano.

Así que se extrae a `app/ingestion/pipeline.py`, y el corte es:

| | responsabilidad |
|---|---|
| `pipeline.py` | qué hacer, y devolver el resultado estructurado |
| los scripts | cómo contarlo a una consola |
| el endpoint | cómo contarlo a una fila de job |

De paso desaparece una duplicación real: `module_files()` y
`corpus_identity()` están copiadas en tres scripts.

### El endpoint

- `POST /corpus/rebuild` — arranca el trabajo y devuelve su id. **No bloquea**:
  medido, trocear son 12,5 s y cargar 141 s contra localhost, y embeber puede ser
  horas si el corpus cambió.
- `GET /corpus/jobs/{id}` — estado, paso actual y lo que produjo cada paso.
- `GET /corpus/jobs` — los últimos trabajos.

El estado va en Postgres y no en memoria: un trabajo de minutos que se pierde
porque el proceso reinició no se puede diagnosticar después.

### El reset, guardado

Se pidió poder limpiar y rehacer. `reset` **borra las filas del corpus**, así que
no alcanza con un booleano en un query param: pide el `tenant_id` y el
`doc_version` explícitos y tiene que coincidir con la configuración. Un `?reset=true`
suelto en un historial de shell no debería vaciar una base.

`--prune`, que ya existe, es lo no destructivo: borra solo lo que el corpus ya no
tiene.

### Una corrida por vez

Dos rebuilds concurrentes escribirían el mismo `data/chunks/` y la misma tabla.
El segundo se rechaza con 409 mientras el primero corre.

## Impact

- `app/ingestion/pipeline.py` y `app/ingestion/jobs.py` nuevos — la ubicación que
  el curso usa para esto.
- `ingestion_jobs` nueva tabla, con migración.
- `app/api/corpus.py` nuevo.
- Los tres scripts pasan a llamar al pipeline. Su salida de consola y sus
  reportes no cambian.
- `Settings.CORPUS_ROOT`, para que el endpoint sepa qué trocear sin recibir una
  ruta por HTTP: aceptar una ruta arbitraria de un cliente es una lectura de
  disco arbitraria.

### Lo que NO hace

- **No sube archivos.** El pipeline lee un directorio local, así que la API tiene
  que correr donde está el corpus. Con una base remota eso funciona; subir 2.169
  archivos por HTTP es otra funcionalidad.
- **No hace falta re-embeber** al cambiar de base: el sidecar es local y se reusa.
  Medido tres veces, un corpus sin cambios de texto cuesta 0 llamadas.

## Why

Un `DATABASE_URL` de Postgres gestionado suele llevar `?sslmode=require`. Con
eso, la aplicación fallaba **solo en el camino async**:

| | driver | resultado |
|---|---|---|
| `alembic upgrade head` | psycopg | funciona |
| `load_pgvector` | psycopg | funciona |
| **`GET /search`** | asyncpg | **falla al conectar** |

Es la peor forma que puede tener una falla: las migraciones y la carga masiva
andan, así que todo parece haber funcionado, y lo único roto es la búsqueda.

### La causa exacta

`asyncpg` **sí** entiende `sslmode`, pero solo dentro de un DSN que parsea él
mismo. El dialecto asyncpg de SQLAlchemy no le pasa un DSN: le pasa kwargs
individuales a `asyncpg.connect()`, cuya firma no tiene `sslmode` **ni**
`**kwargs`. Verificado.

`to_async_url()` solo cambiaba el token del driver y dejaba pasar la query
string intacta, así que `sslmode` llegaba a un parámetro que no existe.

## What Changes

`to_async_url()` renombra `sslmode` a `ssl`, y `to_sync_url()` hace lo inverso.

Es un **renombre y nunca una traducción de significado**: los valores son el
mismo vocabulario —`disable`, `allow`, `prefer`, `require`, `verify-ca`,
`verify-full`— y asyncpg los parsea con su propio `SSLMode.parse`. Hay un test
parametrizado sobre los seis que lo comprueba contra `SSLMode` de asyncpg.

Las dos funciones pasan de manipular strings a usar `make_url` de SQLAlchemy,
que es lo que hace correcta la manipulación de la query. Con un detalle que
tiene test: `render_as_string()` **oculta la contraseña por default**, y una URL
con `***` adentro no conecta con nada.

## Impact

- `app/foundation/persistence/database.py`.
- 7 tests nuevos.
- Sin dependencias nuevas ni migraciones.

### Lo que este cambio corrige de lo que yo había afirmado

Lo vendí varios turnos como «el bloqueador que te queda». **No lo era**: la
`DATABASE_URL` real de este proyecto no lleva `sslmode`, así que `/search`
habría andado igual. Verificado contra la base de Railway: los dos caminos
conectaban ya.

Lo que sí significaba es que la conexión iba **sin TLS** a un proxy público, con
credenciales y datos en claro. Este arreglo no desbloquea la búsqueda: **habilita
poder pedir TLS**. Verificado contra Railway con `?sslmode=require` agregado —
los dos caminos conectan.

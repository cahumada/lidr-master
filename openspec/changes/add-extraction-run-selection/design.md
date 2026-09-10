# Diseño

## 1. La selección vive en nuestro esquema, nunca en el mirror

`visualtime.extraction_runs` tiene un lugar obvio donde poner un `is_active`, y
sería un error. Esa tabla la define y la escribe `dw-oracle-extractor`, que tiene
su propio ciclo de release y su propio DDL: agregarle una columna desde acá
convierte el mirror en un espacio compartido con dos dueños, que es exactamente
la razón por la que vive en un esquema aparte con permisos de solo lectura.

La selección es **nuestra relación con el mirror**, no un atributo del mirror. Va
en `business_db_selection`, en el esquema del servicio, versionada con nuestras
migraciones.

**Una sola activa por tenant, garantizada por la base** —índice parcial único
sobre `status = 'active'`, como el de `corpus_versions`— y no por código: *"la
misma regla sostenida solo en el código de la aplicación se rompe con dos
procesos concurrentes"*.

## 2. La configuración es semilla, no override

`providers_store` tiene los dos mecanismos, y hay que tomar el correcto.

Para las **credenciales** usa override: *"una variable de entorno le gana a una
clave guardada… la copia en la base es el fallback, no la autoridad"*. Para el
**catálogo** usa semilla: *"las tablas se siembran del registro de código y de
`ANSWER_MODEL_CATALOG` en el primer arranque, así una instalación nueva se
comporta exactamente como antes y la consola pasa a ser el lugar donde
cambiarlo"*.

`BUSINESS_DB_RUN_ID` es **semilla**. Con qué corrida del mirror se trabaja es una
decisión de **operación del producto**, no de gestión de secretos: quien opera
está por encima de quien despliega, y una instalación nueva tiene que arrancar
funcionando sin que nadie entre a la consola. Las dos cosas a la vez son
exactamente lo que la semilla resuelve.

Consecuencias concretas:

- El `activate` **nunca** se rechaza por existir un valor en la configuración. El
  `409` por "fijada por el despliegue" no existe: era la variante override.
- No hace falta tocar el `.env` de ningún despliegue para que el admin pueda
  elegir. La variable puede quedar puesta, para siempre, como default.
- **La semilla no se materializa como fila.** Sembrar una insertaría una
  selección que nadie hizo, y después nadie podría distinguir "el default" de "lo
  que eligió alguien". Se resuelve al leer, y la corrida vigente informa su
  origen (`selected` / `default`).

Lo que se pierde con esta elección: no queda forma de **clavar** la corrida desde
el ambiente para una corrida de evals o un incidente. Si esa necesidad aparece, la
respuesta es un candado explícito sobre la selección —y su propio requirement—,
no volver a convertir el default en override.

## 3. El camino de respuesta resuelve del árbol activo, no de la columna

Es la decisión central del change. `window_status` está estampado en 56.537
chunks desde una corrida concreta; si la selección cambia, ese valor queda viejo.

**Alternativa descartada — re-backfill automático al activar.** Es un `UPDATE`
de 56.537 filas: dentro de un request viola *"el rebuild NO DEBE bloquear el
request"*, y como job hereda toda la maquinaria de `app/ingestion/jobs.py` para
un cambio de una columna. Peor: entre la activación y el fin del job las
respuestas mezclan dos corridas, y eso no se ve.

**Alternativa descartada — dejar la columna como autoridad y avisar el
desfasaje.** Funciona, pero deja al motor respondiendo con el estado de una
corrida que ya nadie eligió.

**Lo elegido: una autoridad declarada por uso.**

| uso | autoridad | por qué |
|---|---|---|
| advertencia en el bloque de evidencia | el **árbol activo**, en memoria | es lo que vale al momento de responder, y son 3.389 códigos ya cargados |
| inspección de un chunk, filtro en SQL futuro | la **columna** estampada | es un hecho con procedencia, y sirve sin base de árbol de por medio |

No son dos copias que se desincronizan: es un caché con autoridad declarada. Y
el desfasaje entre ambas deja de ser invisible, porque `business_db_stamp` dice
con qué corrida se estampó el corpus y la consola muestra *"estampado con X ·
activa Y"* con el botón de re-estampar al lado.

Costo: cero. El árbol ya está en memoria para resolver breadcrumbs.

## 4. El caché se resuelve por clave, no por invalidación

`get_navigation_tree` pasa a estar cacheado por `(tenant, env, run_id)`. Activar
otra corrida elige **otra clave**: no hay nada que invalidar, no hay ventana en la
que un worker sirva el árbol viejo y otro el nuevo, y las dos versiones pueden
convivir en memoria mientras terminan los requests en vuelo. Son unos pocos MB.

Pero `get_functional_spec_chunker()` hoy es `@lru_cache` **sin argumentos** y
tiene el árbol adentro. Dejarlo así lo pegaría a la primera corrida que se haya
resuelto en el arranque del proceso, y el bug sería de los peores: dos réplicas
del servicio sirviendo árboles distintos según cuándo arrancó cada una. Ese
singleton tiene que pasar a estar keyed por corrida.

Es el único punto donde este change toca código que ya funcionaba.

## 5. `activated_by` es un dato declarado, y se etiqueta como tal

El servicio no tiene autenticación: `add-console-authentication` pone los roles
en el token de sesión y gatea las rutas **en la consola**. Entonces el servicio no
puede verificar quién activó nada.

Guardarlo igual sirve —cambiar de corrida cambia lo que dice cada respuesta, y
querer saber quién lo hizo es razonable—, pero el campo se llama y se documenta
como **declarado por quien llama**, nunca como identidad verificada. Un audit
trail que parece autoritativo y no lo es es peor que no tenerlo.

**Alternativa descartada — autenticar en el servicio.** Duplicaría el modelo de
roles que la consola ya tiene, para un solo endpoint.

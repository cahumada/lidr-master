# Tareas

## 1. Un solo lugar para la orquestación

- [x] 1.1 `app/ingestion/pipeline.py` con un paso por función, cada uno
      devolviendo un resultado estructurado y reportando por `progress`.
- [x] 1.2 `module_files()` y `corpus_identity()` dejan de estar copiadas en
      tres scripts.
- [x] 1.3 `discover_modules()` y `chunk_module()` se mueven del script al
      pipeline: la app no puede importar de `scripts/`.
- [x] 1.4 Los tres scripts pasan a llamar al pipeline. Su salida de consola y
      sus reportes no cambian, verificado corriéndolos: 2.169 archivos →
      62.228 chunks, 57.131 filas escritas, mismos números que antes.
- [x] 1.5 El manifiesto del sidecar se escribe en el PIPELINE y no en el
      script. Lo había dejado en el script, y eso significaba que el endpoint
      embebía sin dejar su registro autoritativo — justo la divergencia
      silenciosa que la extracción existe para evitar.
- [x] 1.6 Una librería lanza, una CLI traduce a código de salida: los scripts
      capturan `FileNotFoundError`/`ValueError` y devuelven 1 con un renglón, en
      lugar de un traceback. Un test existente lo pedía y lo detectó.

## 2. Seguimiento de trabajos

- [x] 2.1 Tabla `ingestion_jobs` con estado, paso actual, resultado por paso y
      la última línea de progreso. Migración `a01853163726`.
- [x] 2.2 En Postgres y no en memoria: un trabajo de minutos que se pierde
      porque el proceso reinició no se puede diagnosticar después.
- [x] 2.3 Se guarda el mensaje del error y nunca el traceback: esto se lee por
      HTTP.
- [x] 2.4 `run_job` captura toda excepción. Una tarea de background que muere
      sin manejar dejaría la fila clavada en `running` para siempre.
- [x] 2.5 Los pasos corren en un thread: son bloqueantes por dentro y en el
      event loop dejarían la API sin responder durante minutos.

## 3. El endpoint

- [x] 3.1 `POST /corpus/rebuild` devuelve 202 con el id del trabajo.
- [x] 3.2 `GET /corpus/jobs/{id}` y `GET /corpus/jobs`.
- [x] 3.3 Los pasos se reordenan a la única secuencia que funciona, así el
      endpoint no tiene que validar el orden.
- [x] 3.4 `reset` exige `confirm_tenant_id` y `confirm_doc_version`
      coincidentes. Un `reset=true` suelto en un historial de shell no debería
      vaciar una base.
- [x] 3.5 `CORPUS_ROOT` como setting y no como parámetro: aceptar una ruta
      arbitraria por HTTP es una lectura de disco arbitraria.
- [x] 3.6 `CORPUS_ROOT` se exige SOLO si el paso `chunk` está pedido. Exigirla
      siempre bloqueaba el caso más útil que hay: apuntar el servicio a una base
      nueva y cargarle el corpus que ya está en disco.

## 4. Una corrida por vez

- [x] 4.1 El endpoint chequea si hay un trabajo corriendo y responde 409.
- [x] 4.2 **Y la base lo garantiza.** El chequeo de la aplicación es una carrera
      que dos procesos pierden, y se perdió: dos rebuilds pasaron y se trabaron
      entre sí —uno borrando 57.101 filas, el otro copiando sobre ellas— con un
      `DeadlockDetected` de Postgres. Índice único parcial
      `uq_ingestion_jobs_one_running`, la misma técnica que ya usa
      `corpus_versions` para su única versión activa. Migración `3d59e9c3abb5`.
- [x] 4.3 `create_job` traduce el rechazo de la base a `AlreadyRunning`, y el
      endpoint a 409. Verificado insertando dos veces sin chequear antes.

      **No reproduje el interleaving exacto** del deadlock original: bajo
      `TestClient` las tareas de background corren hasta el final antes de que
      vuelva el request, así que ahí no se solapan. Lo que está probado es que
      se solaparon —el mensaje de Postgres lo dice— y que la garantía ahora es
      de la base y no del código de la aplicación.

## 5. Tests

- [x] 5.1 El orden de los pasos, incluido un paso inventado que se descarta.
- [x] 5.2 Las guardas del endpoint, con la sesión falseada: reset sin
      confirmar, reset con otro corpus, chunk sin raíz, load sin raíz, segundo
      rebuild, job inexistente.
- [x] 5.3 El pipeline: el manifiesto no es un módulo, la identidad sale del
      manifiesto, podar un corpus parcial se rechaza, los dos manifiestos tienen
      nombres distintos.
- [x] 5.4 El índice parcial existe y es único. 20 tests nuevos, 464 en total.

## 6. Cierre

- [x] 6.1 `pytest`, `pytest -m integration`, `ruff check .` y `validate_specs`
      en verde.
- [x] 6.2 Verificado punta a punta por HTTP: `chunk` + `embed` sobre `claims`,
      y `load` completo. El pipeline entero corre sin tocar una terminal.
- [x] 6.3 Promover el delta y archivar.

# Tareas

- [x] 1.1 `to_async_url()` renombra `sslmode` a `ssl`; `to_sync_url()` lo
      inverso.
- [x] 1.2 Las dos usan `make_url` en lugar de manipular strings.
- [x] 1.3 `render_as_string(hide_password=False)`: el default oculta la
      contraseña y una URL con `***` no conecta con nada. Fijado por test.
- [x] 2.1 Test de los dos sentidos y del viaje redondo.
- [x] 2.2 Test parametrizado sobre los seis modos de libpq, comprobando contra
      el `SSLMode` de asyncpg que es el mismo vocabulario.
- [x] 2.3 Test de que una URL sin modo TLS no se toca.
- [x] 3.1 Verificado contra la base real de Railway: pgvector 0.8.6, los dos
      caminos conectan, y con `?sslmode=require` agregado también.
- [x] 3.2 `pytest` (498), `ruff check .` y `validate_specs` en verde.
- [x] 3.3 Un test mal aislado que escribí yo —`test_chunking_without_a_configured_root_is_refused`—
      limpiaba `CORPUS_ROOT` y no `CORPUS_BUCKET`, así que dependía del `.env` de
      la máquina y falló cuando el `.env` real pasó a tener bucket. Ahora fija
      las dos, y se agregó el caso de que un bucket solo alcanza.
- [x] 3.4 Promover el delta y archivar.

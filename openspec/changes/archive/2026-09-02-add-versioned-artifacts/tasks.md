# Tareas

- [x] 1.1 `version_slug()`: slug del `doc_version` más una huella del valor
      original. La huella no es adorno — sin ella `2026.1`, `2026 1` y `2026-1`
      dan el mismo slug y dos versiones compartirían directorio, mezclando
      corpus en silencio.
- [x] 1.2 `corpus_dir(base, doc_version)`: un solo lugar que sabe el layout.
- [x] 1.3 Los tres pasos resuelven su directorio: `chunk_corpus` escribe bajo la
      versión que le pasan, `embed_corpus` y `load_corpus` leen bajo
      `settings.DOC_VERSION`.
- [x] 1.4 `corpus_identity()` verifica que el manifiesto coincida con el
      directorio que lo contiene. Un desajuste significa que alguien movió
      archivos, y cargar un corpus atribuyéndolo a otra versión no se ve
      después: las filas quedan con la versión equivocada y el prune de la
      versión real las borra.
- [x] 1.5 Cada resultado lleva su directorio resuelto (`out_dir`,
      `chunks_dir`), así el reporte del script cae al lado de los artefactos.
      Lo había dejado escribiendo en la base y un test lo detectó.

- [x] 2.1 El tenant NO va en la ruta. Un proceso sirve exactamente un tenant, así
      que un segmento por tenant sería un nivel que nunca tiene hermanos — el
      mismo knob especulativo que ya salió del prefijo del bucket.

- [x] 3.1 Los tres scripts que leen el corpus sin pasar por el pipeline
      —`build_process_map`, `draft_golden_set`, `audit_dangling_chunks`—
      resuelven la versión. Sin esto los habría roto en silencio, porque
      seguirían mirando la base vacía.
- [x] 3.2 Artefactos existentes movidos: 32 archivos de corpus y 58 de sidecar.

- [x] 4.1 Tests nuevos: dos versiones que slugifican igual no comparten
      directorio; el slug es un nombre de directorio usable; un manifiesto que no
      coincide con su directorio es un error.
- [x] 4.2 La fixture de `test_embed_corpus_script` fija la versión en lugar de
      leerla del `.env`: los pasos de lectura resuelven su directorio desde
      Settings, así que el test tiene que controlarla o depende de la máquina.
- [x] 4.3 Verificado que dos versiones conviven: `2026.1` y `2026.2` en
      directorios separados, cada una con su manifiesto correcto.
- [x] 4.4 Verificado que el pipeline encuentra los artefactos movidos:
      `embed --dry-run` reporta 0 para embeber y 57.131 reusadas; `load
      --dry-run` reporta 62.228 filas listas y 0 sin vector.
- [x] 4.5 `pytest` (484), `ruff check .` y `validate_specs` en verde.
- [x] 4.6 Promover el delta y archivar.

## Lo que queda anotado

- [ ] 5.1 **El sidecar sigue descartando entre corpus.**
      `dropped = len(known - corpus_hashes)` saca del sidecar los vectores que no
      están en el corpus actual. Con el directorio por versión eso ya no cruza
      versiones, pero `EmbeddingIndexEntry` **registra** `tenant_id` y
      `doc_version` por entrada y `rows_by_hash()` los **ignora**: la información
      para reusar entre corpus está escrita en el archivo y no se usa.

      Reusar entre versiones ahorraría de verdad —un texto que no cambió entre
      `2026.1` y `2026.2` es el mismo vector— pero ahora cada versión tiene su
      sidecar, así que se paga de nuevo. Es US$ 0,10 por corpus completo, así que
      no es urgente; es un desperdicio conocido.

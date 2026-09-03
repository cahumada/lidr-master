# Tareas

- [x] 1.1 `ChunkMetadata.source_type`, `str` y no `Literal`, default
      `functional_spec`.
- [x] 1.2 `chunks.source_type` dentro de la clave única, más
      `ix_chunks_source_type`. Migración `62457660a177` con `server_default`.
- [x] 1.3 `SearchFilters.source_type` y su predicado en el WHERE.
- [x] 1.4 En `COPY_COLUMNS` y NO en `_METADATA_COLUMNS`: es identidad, así que
      un conflicto no la reescribe.
- [x] 1.5 `DISTINCT ON` y `ON CONFLICT` actualizados a la clave de cuatro
      columnas.
- [x] 1.6 El chunker lo estampa explícito, para que el default nunca decida.
- [x] 2.1 Tests: la clave única lleva las cuatro columnas; `source_type` no está
      entre las de metadata; viaja en el COPY; `None` es el default de búsqueda;
      el filtro recorta.
- [x] 2.2 El test de integración derivaba su fila de `COPY_COLUMNS` y detectó la
      deriva solo — 16 fallas hasta agregarle el campo.
- [x] 3.1 Migrado, corpus regenerado (62.228 chunks), re-embed 0 llamadas, store
      recargado, filtro verificado contra la base.
- [x] 3.2 Registrar la restricción en `openspec/project.md`, con la regla: si la
      decisión queda escrita en la base se toma ahora; si vive solo en código,
      espera.
- [x] 3.3 Corregir en `project.md` lo que había quedado vencido: la
      justificación de no replicar `app/ingestion/` («sin persistencia», falso
      desde pgvector), el árbol de arquitectura, el stack, y «Estado y alcance»,
      que declaraba embeddings, pgvector y búsqueda semántica como no
      construidos.
- [x] 4.1 `pytest`, `pytest -m integration`, `ruff check .` y `validate_specs`
      en verde.
- [x] 4.2 Promover el delta y archivar.

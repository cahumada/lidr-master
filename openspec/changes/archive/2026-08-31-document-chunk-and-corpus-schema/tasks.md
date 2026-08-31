# Tareas de implementación

## 1. Contrato de datos del chunk

- [x] 1.1 Nueva capability `chunk-schema`, escrita leyendo
      `app/generation/rag/schemas.py` campo por campo, no de memoria.
- [x] 1.2 Documentar los cuatro modelos con sus roles distintos: `Chunk`
      (texto embebible + metadata filtrable + presupuesto medido),
      `ChunkMetadata`, `Reference`, `ChunkedDocument`.
- [x] 1.3 Declarar las invariantes que hoy solo viven en tests: formato y
      unicidad de `chunk_id`, `token_count` incluye el header contextual,
      un chunk nunca se auto-referencia.
- [x] 1.4 Declarar la **semántica de la ausencia**: un campo opcional ausente
      significa "no resuelto", no "vacío". Es la garantía que evita que un
      consumidor rellene `module_code` por su cuenta.
- [x] 1.5 Declarar la presencia condicional de `field` (solo `table`) y
      `bullet_path` (solo `narrative`).

## 2. Forma del corpus en disco

- [x] 2.1 Documentar la forma de `<módulo>.json` verificada contra el artefacto
      real: claves `module` y `documents`, y los dos campos de procedencia
      (`source_file`, `module`) que el modelo no lleva.
- [x] 2.2 Declarar que un archivo puede aportar **varias** entradas de
      documento — un consumidor que asuma una por archivo pierde transacciones.
- [x] 2.3 Documentar `data/windows_tree.csv` como artefacto de entrada
      versionado (tres columnas, conversión reproducible, opcional).
- [x] 2.4 Ampliar el requirement del reporte: documentos puede ser mayor que
      archivos, y eso es cobertura, no un error de suma.

## 3. Defecto encontrado al documentar

- [x] 3.1 Medido: **133 documentos (5,9%) y 2968 chunks (4,5%)** tenían
      `document_title` = su propia línea de id, dejando headers contextuales
      como `[Documento: OP010 - `**(OP010)**`]`.
- [x] 3.2 Causa: al segmentar por línea de id (cambio anterior, grupo 1), un
      bloque que arranca ahí no tiene H1 propio, y el fallback "primera línea no
      vacía" devolvía la línea de id.
- [x] 3.3 `extract_document_title()` saltea líneas de id y headings de sección.
- [x] 3.4 `extract_block_title()` nuevo, **más estricto**: el título propio de
      un bloque es su H1 o nada. Primer intento fallido: solo saltear la línea
      de id hacía que devolviera la primera línea de prosa del cuerpo
      (`[Documento: CA014 - Permite consultar y modificar.]`), así que el
      fallback al título del documento nunca se activaba.
- [x] 3.5 Un bloque sin título propio cae al título del documento.
- [x] 3.6 Tests de regresión: ningún `document_title` puede ser un bloque de id,
      y `CA014` recupera "Coberturas de la póliza individual o certificado".
      El test viejo no lo detectaba porque solo verificaba `assert title`.
- [x] 3.7 Verificado sobre el corpus completo: 133 → **0**.

## 4. Cierre

- [x] 4.1 Corpus regenerado: 2250 documentos, 66.634 chunks, 5.430.585 tokens.
      Los +16 chunks respecto de la corrida anterior son los títulos ahora
      recuperados, que cambian el header contextual y por lo tanto el
      presupuesto de tokens de algunos chunks narrativos.
- [x] 4.2 `uv run pytest` (115 tests), `uv run ruff check .` y
      `uv run python scripts/validate_specs.py` en verde.
- [x] 4.3 Deltas integrados en `openspec/specs/` y cambio archivado.

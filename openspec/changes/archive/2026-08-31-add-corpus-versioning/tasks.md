# Tareas de implementación

## 1. Identidad de versión

- [x] 1.1 `tenant_id` y `doc_version` en `ChunkMetadata` — es la fila que el
      vector store filtra. Con defaults placeholder solo para no arrastrar los
      campos por cinco firmas de chunking.
- [x] 1.2 `TENANT_ID` y `DOC_VERSION` en `Settings`, cableados por la raíz de
      composición, con flags `--tenant` / `--doc-version` en el batch.
- [x] 1.3 `source_revision` y `valid_from` en `ChunkedDocument`, ausentes
      cuando no se conocen (el markdown no los lleva).
- [x] 1.4 Clave compuesta `(tenant_id, doc_version, chunk_id)` declarada en la
      spec: `chunk_id` queda como localizador estable entre versiones, no como
      identidad única.
- [x] 1.5 Test: mismo documento para dos tenants → mismo `chunk_id`, distinto
      `tenant_id`.

## 2. Hash de contenido

- [x] 2.1 `content_hash(text)` con SHA-256, un solo helper.
- [x] 2.2 Hash por **documento** (fuente normalizada del bloque) → una
      reingesta puede saltear un documento sin cambios.
- [x] 2.3 Hash por **chunk** (su `text` completo, header incluido) → un hash
      igual entre corridas significa que el embedding existente sigue válido.
- [x] 2.4 Se hashea sobre el texto normalizado: un re-export que solo cambió
      fines de línea no parece un cambio de contenido. Con test.
- [x] 2.5 Test del payoff: editar una regla cambia el hash del documento pero
      deja >80% de los hashes de chunk intactos.

## 3. Manifiesto del corpus

- [x] 3.1 `CorpusManifest` en el contrato y `data/chunks/manifest.json` en la
      salida, con `corpus_id`, tenant, versión, timestamp, raíz, módulos y totales.
- [x] 3.2 Los campos nuevos del documento (`content_hash`, `source_revision`,
      `valid_from`) se persisten en los JSON por módulo.

## 4. Bug encontrado al verificar

- [x] 4.1 **27.813 chunks (42%) quedaron con tenant/version placeholder.**
      Causa: en `absorb()`, el camino de un documento que ya existe estampaba
      solo `transaction_type` y `document_kind` en el segundo lote de chunks.
      Eso significa que **también les faltaba el breadcrumb** desde el grupo 3
      del cambio anterior — un defecto que estaba ahí y nadie había medido.
- [x] 4.2 Estampado unificado en un único helper `_stamp()`, usado por los dos
      caminos que producen chunks.
- [x] 4.3 Test de regresión con `accounting_cpl500.md` (un documento que
      fusiona preámbulo y bloque): todos sus chunks deben coincidir en su
      estampado. Verificado sobre el corpus: 27.813 → **0**.

## 5. Cierre

- [x] 5.1 Corpus regenerado: 2250 documentos, 66.634 chunks, manifiesto
      presente, 0 chunks sin estampar.
- [x] 5.2 `uv run pytest` (125 tests), `ruff` y `validate_specs` en verde.
- [x] 5.3 Deltas integrados en `openspec/specs/` y cambio archivado.

## 6. Hallazgo que habilita el hash, y que NO se resuelve acá

- [x] 6.1 Medido gracias al `content_hash`: **6570 chunks (9,9%) son
      duplicados exactos** de otro chunk del mismo documento.
- [x] 6.2 Al inspeccionarlos apareció la causa, que es más grande que la
      duplicación: **14.930 chunks (22,4%) son degenerados** — ≤6 palabras de
      contenido real — y consumen **658.063 tokens (12,1%)**. Los más
      frecuentes son headings sobrantes y artefactos del export:
      `'###  Proceso'` (x200), `'__'` (x179), `'No aplica.'` (x178),
      `'####  Campo'` (x169), `'####  Operador'` (x162).
      Varios `####` sugieren bloques de tabla rota que la reparación no alcanzó.
- [x] 6.3 **No se resuelve en este cambio.** Es calidad de chunk, no
      versionado, y trae las mismas decisiones que tuvo el documento índice
      (¿descartar o marcar? ¿qué umbral?). Merece su propio proposal con la
      evidencia medida, no un filtro improvisado acá.

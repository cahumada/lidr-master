## Why

El contrato de datos del chunk y la forma del corpus generado son lo que va a
consumir la capa de embeddings y, después, pgvector. Hoy están **implícitos**:
viven en los `Field(description=...)` de `app/generation/rag/schemas.py` y en
lo que `scripts/chunk_corpus.py` decide escribir. Nada normativo dice qué
campos existen, cuándo están presentes, ni qué invariantes se cumplen.

Eso importa ahora y no después por tres razones concretas:

1. **La capa siguiente depende de estos campos.** El embedder y el store van a
   leer `text`, `token_count`, y filtrar por `metadata`. Si el contrato no está
   escrito, cada consumidor va a inferirlo del JSON que le toque ver.
2. **Los campos opcionales significan algo.** `module_code` ausente no es
   "vacío": es "el export de `WINDOWS` no resuelve camino para este código".
   Sin escribirlo, un consumidor lo va a tratar como dato faltante y lo va a
   rellenar.
3. **Hay invariantes que hoy solo viven en tests.** Que `chunk_id` sea único,
   que `token_count` incluya el header contextual, que un chunk nunca se
   referencie a sí mismo: son garantías reales que un consumidor debería poder
   asumir, y para eso tienen que estar declaradas.

Al escribir esta documentación apareció además un defecto real (ver más abajo),
que es exactamente el tipo de cosa que un contrato escrito hace visible.

## What Changes

- **Nueva capability `chunk-schema`**: el contrato de datos, campo por campo —
  `Chunk`, `ChunkMetadata`, `Reference`, `ChunkedDocument` — con sus
  invariantes y la semántica de cada campo opcional.
- **`corpus-batch-chunking` crece** con la forma del artefacto en disco: qué
  contiene cada `<módulo>.json`, el reporte, y el CSV del árbol `WINDOWS` como
  artefacto de entrada.
- **Fix encontrado documentando**: el título de un bloque que arranca en su
  propia línea de id era esa línea de id.

## Capabilities

### Capabilities nuevas

- `chunk-schema`: el contrato de datos de un chunk y del documento troceado,
  con sus invariantes.

### Capabilities modificadas

- `corpus-batch-chunking`: la forma del corpus generado en disco y su
  artefacto de entrada.
- `document-chunking`: el título de un bloque sin H1 propio cae al del
  documento, en vez de tomar su línea de id.

## Impact

- `openspec/specs/chunk-schema/spec.md` — nueva.
- `openspec/specs/corpus-batch-chunking/spec.md` — artefacto en disco.
- `openspec/specs/document-chunking/spec.md` — regla de título.
- `app/generation/rag/chunking/functional_spec.py` — `extract_block_title()`
  nuevo; `extract_document_title()` saltea líneas de id y headings.
- `tests/generation/rag/test_transaction_attribution.py` — tests de regresión
  del título.

## Defecto encontrado al documentar

Inspeccionando el artefacto real para describirlo, `CA014` tenía
`document_title` = `` `(CA014)` `` en vez de "Coberturas de la póliza
individual o certificado". Causa: el grupo 1 del cambio anterior pasó a
segmentar por línea de id, y un bloque que arranca ahí no tiene H1 propio, así
que el fallback "primera línea no vacía" devolvía la propia línea de id.

Alcance medido: **133 documentos (5,9%) y 2968 chunks (4,5%)** con un header
contextual que no dice nada de la transacción
(`[Documento: OP010 - `**(OP010)**`]`).

El test existente no lo detectó porque solo verificaba `assert title` —
no vacío. Corregido y fijado con tests: 133 → **0**.

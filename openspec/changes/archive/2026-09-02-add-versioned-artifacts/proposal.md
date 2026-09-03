## Why

`data/chunks` y `data/embeddings` eran rutas fijas, y la base **no**: la
identidad de una fila es `(tenant_id, doc_version, source_type, content_hash)`.
El esquema era multi-versión y los artefactos de disco no.

Demostrado con dos corpus: de 384 chunks del primero sobrevivieron **0** al
trocear el segundo encima, y el manifiesto quedó declarando la última versión,
así que `load_corpus` habría cargado todo con esa.

El riesgo cercano no es el multi-tenant: es `doc_version`. Hoy vale
`DW Funtionals 2026.1`, y ese `.1` dice que va a haber un `.2`.

Nada de esto corrompe la base —todo lo de disco es dato derivado— pero re-armarlo
cuesta 2.172 llamadas al bucket y ~446 lotes de embeddings.

## What Changes

Cada versión tiene su directorio: `data/chunks/<slug>/` y
`data/embeddings/<slug>/`.

El slug lleva **una huella del valor original**, y no es adorno: sin ella
`2026.1`, `2026 1` y `2026-1` producen el mismo slug y dos versiones distintas
compartirían directorio, **mezclando corpus en silencio**.

Y el manifiesto de adentro tiene que **coincidir** con el directorio que lo
contiene. Un desajuste significa que alguien movió archivos, y cargar un corpus
atribuyéndolo a otra versión es un error que no se ve: las filas quedan con la
versión equivocada y el prune de la versión real las borra.

### El tenant NO va en la ruta

Un proceso sirve exactamente un tenant: `Settings.TENANT_ID` es un valor único
leído en `/search`, en el rebuild y en el chunker. Un segmento por tenant sería
un nivel de directorio que nunca tiene hermanos — el mismo knob especulativo que
ya saqué del prefijo del bucket.

Para servir varios clientes, la recomendación es **un deploy por tenant**, que
funciona hoy sin código: contenedores separados son discos separados. Y ahí el
argumento medible es el índice HNSW: **446 MB de los 1.033 GB que pesa un
tenant-versión**. HNSW es un grafo y el `WHERE tenant_id` se aplica después, así
que buscar para un cliente camina por los vectores de los otros — la misma clase
de degradación que ya obligó a poner `hnsw.iterative_scan = strict_order` cuando
una búsqueda filtrada devolvió 0 filas de 7.461 que matcheaban.

## Impact

- `version_slug()` y `corpus_dir()` en el pipeline.
- Los tres pasos resuelven su directorio; los resultados llevan el resuelto, así
  el reporte del script cae al lado de los artefactos y no en la base.
- Los tres scripts que leen el corpus sin pasar por el pipeline
  —`build_process_map`, `draft_golden_set`, `audit_dangling_chunks`— resuelven la
  versión también. Sin eso los habría roto en silencio.
- Los artefactos existentes se movieron a su directorio: 32 archivos de corpus y
  58 de sidecar, verificado con `--dry-run` de embeddings (0 para embeber) y de
  carga (62.228 filas listas, 0 sin vector).

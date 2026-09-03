# Tareas

## 1. Diagnóstico previo

- [x] 1.1 Medido `document_kind` en el corpus completo: 443 de 56.537 chunks
      (0,8%), 34 de 2.177 documentos (1,6%) son `'index'`.
- [x] 1.2 Verificado que 2 documentos anotados como relevantes en el golden
      set (`SI001_A`, `DP003_A`) son `document_kind='index'` — el riesgo que
      terminó confirmándose.
- [x] 1.3 Verificado con una consulta real que `document_kind='index'` puede
      dominar el top-10 (6 de 10) muy por encima de su participación en el
      corpus.
- [x] 1.4 Verificado que `document_kind` existía como filtro binario opcional
      y en ningún lugar del ranking.

## 2. Plumbing

- [x] 2.1 `document_kind` agregado a `_SELECTED`, `SearchHit`, `RankedHit` en
      el repositorio — un solo lugar (`_ranked()`) cubre `search_lexical`,
      `search_exact` y `by_content_hashes`.
- [x] 2.2 `RetrievedChunk.document_kind`, poblado en `retrieve()`.
- [x] 2.3 Expuesto en `SearchHit` (schema Pydantic) y en la respuesta de
      `GET /search`.

## 3. Los dos mecanismos, parametrizados

- [x] 3.1 `_demote_index_kind()`: multiplica el score RRF de un candidato
      `'index'` por `penalty` y reordena. Soft, no un filtro — verificado que
      un candidato índice puede seguir ganando si es la única evidencia.
- [x] 3.2 `_dedupe_by_text()`: descarta un candidato cuyo cuerpo (header
      `[Documento: ...]` stripeado) ya apareció, se queda con la ocurrencia
      mejor rankeada.
- [x] 3.3 `_body_of()`: el header es exactamente la primera línea; todo lo
      demás es sección + cuerpo.
- [x] 3.4 `index_penalty`/`dedupe_text` como parámetros de `retrieve()` y
      `_fuse_branches()`, propagados también a la fusión de subconsultas de
      la descomposición.
- [x] 3.5 12 tests unitarios, sin red ni base.

## 4. Medición — y el resultado que decidió todo

- [x] 4.1 Barrido de `index_penalty` (1,0 / 0,5 / 0,3 / 0,1 / 0,0) contra las
      35 preguntas humanas, sin reranker ni descomposición para aislar el
      efecto [VERIFICADO-CORPUS]:

      | penalty | top10 | rango | perdidos | p@10 | `SI001_A` | `DP003_A` |
      |---|---:|---:|---:|---:|---:|---:|
      | 1,0 (sin cambios) | **50** | 18 | 17 | **0,143** | 12 | **5** |
      | 0,5 | 49 | 19 | 17 | 0,140 | 23 | 39 |
      | 0,1 | 49 | 19 | 17 | 0,140 | 24 | 56 |

      **Pérdida neta con cualquier magnitud.** `DP003_A` explica todo el
      retroceso: estaba en el puesto 5 (top-10) sin tocar nada, y cae a 34-58
      con cualquier penalización.

- [x] 4.2 Medido `dedupe_text` solo (`penalty=1,0`):

      | | top10 | rango | perdidos | p@10 |
      |---|---:|---:|---:|---:|
      | sin cambios | 50 | 18 | **17** | 0,143 |
      | dedupe solo | 49 | 17 | **19** | 0,140 |

      `perdidos` sube: dos pares se caen del candidato de 60.

- [x] 4.3 Diagnosticado con precisión, contra la base, cuáles pares y por
      qué: `CAC1005B`→sobrevive `CAC1005A` (cuerpo idéntico);
      `CAC1006`→sobrevive `CAC1006B` (cuerpo idéntico). Confirma la
      hipótesis: el dedup confunde texto idéntico con documento
      intercambiable, y el golden set anota por `document_id` exacto.

- [x] 4.4 **Decisión: ningún mecanismo queda activado por default.**
      `index_penalty=1.0`, `dedupe_text=False` — los valores que la
      medición sostiene.

## 5. Cierre

- [x] 5.1 `pytest` (496 pasan, 0 rotos), `ruff check .` en verde.
- [x] 5.2 Ninguno de los dos parámetros se expone en `GET /search`: no hay
      ningún valor medido que valga la pena ofrecer.
- [x] 5.3 Promover el delta (solo la exposición de `document_kind` en la
      API, que es lo único que efectivamente cambia el comportamiento
      observable) y archivar.

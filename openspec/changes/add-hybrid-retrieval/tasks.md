# Tareas de implementación

## 1. La métrica primero

- [ ] 1.1 `scripts/eval_retrieval.py`: recall@1/5/10 sobre los documentos de
      título único, con `--limit` para muestrear y `--full` para los 1.871.
- [ ] 1.2 Registrar la línea base del vector solo, con la muestra completa.
- [ ] 1.3 Escribir en el reporte los límites de la métrica, no solo el número.

## 2. Los tres caminos

- [ ] 2.1 `search_lexical()` en el repositorio: full-text español con OR
      ponderado, `ts_rank_cd`, mismos filtros estructurales que el vectorial.
- [ ] 2.2 `search_exact()`: por `document_id`, por `field` y por coincidencia
      literal en el texto.
- [ ] 2.3 Detector de forma de identificador, para no correr el camino exacto en
      una pregunta en lenguaje natural.
- [ ] 2.4 Tests unitarios del SQL de cada camino, sin base.

## 3. Fusión

- [ ] 3.1 `fusion.py` con RRF: `peso / (k + posición)`, pesos por camino en
      `Settings`.
- [ ] 3.2 Tope opcional de chunks por documento, con default que no recorta.
- [ ] 3.3 Tests: un resultado que sale en dos caminos le gana a uno que sale
      primero en uno solo; el tope por documento recorta lo que dice recortar.

## 4. Verificación contra la línea base

- [ ] 4.1 `CAC011` devuelve el documento CAC011 en el primer puesto.
- [ ] 4.2 `codigo de error 10208` devuelve los chunks que contienen 10208.
- [ ] 4.3 `premium_mo` y `nReceipt` devuelven chunks que contienen el término.
- [ ] 4.4 recall@k con la fusión, contra la línea base. Si baja, entender por qué
      antes de seguir.
- [ ] 4.5 Medir qué le hace el tope por documento a la métrica.

## 5. Endpoint

- [ ] 5.1 `GET /search` con la consulta y los filtros como query params.
- [ ] 5.2 La respuesta lleva la procedencia de cada hit: documento, sección,
      breadcrumb y de qué camino vino.
- [ ] 5.3 Tests del router con la capa de retrieval mockeada.

## 6. Cierre

- [ ] 6.1 `pytest`, `pytest -m integration`, `ruff` y `validate_specs` en verde.
- [ ] 6.2 Promover el delta y archivar.

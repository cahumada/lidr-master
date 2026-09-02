# Tareas de implementación

## 1. Las métricas primero

- [ ] 1.1 `scripts/eval_retrieval_proxy.py`: acierto@1/5/10 sobre los documentos
      de título único, con `--limit` para muestrear y `--full` para los 1.871.
- [ ] 1.2 El reporte del proxy declara que es un proxy y enumera sus límites.
- [ ] 1.3 Registrar la línea base del vector solo, con la muestra completa.
- [ ] 1.4 `evals/golden_retrieval.json`: 20-30 preguntas borradoreadas de
      secciones reales, cada una con sus documentos relevantes y con
      distractores deliberados. Marcado como PENDIENTE DE REVISIÓN.
- [ ] 1.5 `scripts/eval_retrieval.py`: precision@k y latencia por configuración
      con nombre, como el `eval_retrieval_s10.py` del curso.
- [ ] 1.6 Mientras el golden set no esté revisado, su reporte lo dice.

## 2. Los tres caminos

- [ ] 2.1 `search_lexical()` en el repositorio: full-text español con OR
      ponderado, `ts_rank_cd`, mismos filtros estructurales que el vectorial.
- [ ] 2.2 `search_exact()`: por `document_id`, por `field` y por coincidencia
      literal en el texto.
- [ ] 2.3 Detector de forma de identificador, para no correr el camino exacto en
      una pregunta en lenguaje natural.
- [ ] 2.4 Tests unitarios del SQL de cada camino, sin base.

## 3. Fusión

- [ ] 3.1 `fusion.py` con RRF: `1 / (k + posición)`, `k = 60`, SIN pesos por
      rama (el curso deliberadamente no los tiene).
- [ ] 3.2 Tope opcional de chunks por documento, con default que no recorta.
- [ ] 3.3 Tests: un resultado que sale en dos caminos le gana a uno que sale
      primero en uno solo; el tope por documento recorta lo que dice recortar.
- [ ] 3.4 Test: la contribución depende solo de la posición y de `k`.

## 4. Verificación contra la línea base

- [ ] 4.1 `CAC011` devuelve el documento CAC011 en el primer puesto.
- [ ] 4.2 `codigo de error 10208` devuelve los chunks que contienen 10208.
- [ ] 4.3 `premium_mo` y `nReceipt` devuelven chunks que contienen el término.
- [ ] 4.4 El proxy con la fusión, contra la línea base. Si baja, entender por qué
      antes de seguir.
- [ ] 4.5 precision@k sobre el golden set, por configuración: solo vector, solo
      léxico, y la fusión.
- [ ] 4.6 Medir qué le hace el tope por documento a las dos métricas.

## 5. Endpoint

- [ ] 5.1 `GET /search` con la consulta y los filtros como query params.
- [ ] 5.2 La respuesta lleva la procedencia de cada hit: documento, sección,
      breadcrumb y de qué camino vino.
- [ ] 5.3 Tests del router con la capa de retrieval mockeada.

## 6. Lo que el curso tiene y este cambio no

- [ ] 6.0 Dejar anotado en el archive: `retrieval/reranker.py`,
      `query_transform.py` y `router.py` existen en el curso y quedan afuera a
      propósito. Medir primero la fusión sola, después agregar.

## 7. Cierre

- [ ] 6.1 `pytest`, `pytest -m integration`, `ruff` y `validate_specs` en verde.
- [ ] 6.2 Promover el delta y archivar.

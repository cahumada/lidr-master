# Tareas de implementación

## 1. Las métricas primero

- [x] 1.1 `scripts/eval_retrieval_proxy.py`: acierto@1/5/10 sobre los documentos
      de título único, con `--limit` para muestrear y `--full` para los 1.871.
- [x] 1.2 El reporte del proxy declara que es un proxy y enumera sus límites.
- [x] 1.3 Registrar la línea base del vector solo, con la muestra completa.
- [ ] 1.4 `evals/golden_retrieval.json`: 20-30 preguntas borradoreadas de
      secciones reales, cada una con sus documentos relevantes y con
      distractores deliberados. Marcado como PENDIENTE DE REVISIÓN.
- [ ] 1.5 `scripts/eval_retrieval.py`: precision@k y latencia por configuración
      con nombre, como el `eval_retrieval_s10.py` del curso.
- [ ] 1.6 Mientras el golden set no esté revisado, su reporte lo dice.

## 2. Los tres caminos

- [x] 2.1 `search_lexical()` en el repositorio: full-text español con OR
      ponderado, `ts_rank_cd`, mismos filtros estructurales que el vectorial.
- [x] 2.2 `search_exact()`: por `document_id`, por `field` y por coincidencia
      literal en el texto.
- [x] 2.3 Detector de forma de identificador, para no correr el camino exacto en
      una pregunta en lenguaje natural.
- [x] 2.4 Tests unitarios del SQL de cada camino, sin base.

## 3. Fusión

- [x] 3.1 `fusion.py` con RRF: `1 / (k + posición)`, `k = 60`, SIN pesos por
      rama (el curso deliberadamente no los tiene).
- [x] 3.2 Tope opcional de chunks por documento, con default que no recorta.
- [x] 3.3 Tests: un resultado que sale en dos caminos le gana a uno que sale
      primero en uno solo; el tope por documento recorta lo que dice recortar.
- [x] 3.4 Test: la contribución depende solo de la posición y de `k`.

## 4. Verificación contra la línea base

- [x] 4.1 `CAC011` devuelve el documento CAC011 en el primer puesto.
- [x] 4.2 `codigo de error 10208` devuelve los chunks que contienen 10208.
- [x] 4.3 `premium_mo` y `nReceipt` devuelven chunks que contienen el término.
- [x] 4.4 El proxy con la fusión, contra la línea base. Si baja, entender por qué
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


## Estado: implementado hasta la medición, y la medición cambió una decisión

Hecho: los tres caminos, la fusión RRF sin pesos, el tope por documento, el
detector de identificadores, el proxy de evaluación y 40 tests unitarios.

**Pendiente y bloqueado en revisión humana:** el golden set y `precision@k`
sobre él (1.4-1.6, 4.5-4.6), y el endpoint (5.x).

## El hallazgo que cambió el default

Los tres casos que motivaban el cambio quedaron arreglados. `CAC011` devuelve
los chunks de `CAC011` en los cinco primeros puestos, todos con el término
literal; antes el documento no aparecía. Igual `premium_mo`, `nReceipt` y
`10208`.

Pero el proxy dice otra cosa sobre la fusión completa. Medido sobre 250
documentos, semilla 11:

| config | acierto@1 | @5 | @10 | ms/consulta |
|---|---:|---:|---:|---:|
| `vector` | **77%** | 93% | 94% | 66 |
| `lexical` | 12% | 28% | 37% | 111 |
| `vector` + `exact` | **77%** | 93% | 94% | 402 |
| los tres | **48%** | 90% | 94% | 567 |

Agregar la rama léxica se lleva 29 puntos de acierto@1. Y con muestra de 60 y
semilla 7 el patrón es el mismo (62% → 43%), así que no es ruido.

**Pero el patrón completo dice algo más preciso.** El @10 es *idéntico* (94% vs
94%) y el @5 casi no se mueve. La fusión **no pierde la respuesta**: la mete en
el conjunto candidato y deja de ponerla primera.

Eso no es "la rama léxica es mala". Es que **el trabajo de la fusión es el recall
del conjunto candidato, y la precisión arriba es del reranker** — la pieza que
este cambio dejó afuera a propósito. El curso tiene las dos; yo implementé una
sola y medí el resultado de la mitad.

Diferir el reranker fue la decisión equivocada, no incluir la rama léxica.

**Qué se hizo con eso:** el default pasa a `(vector, exact)`, que es lo que la
medición sostiene hoy, y `lexical` queda a un argumento de distancia para cuando
entre el reranker. `ALL_BRANCHES` existe y el proxy lo mide.

No dejé el default en los tres caminos: shipear una configuración medida como
peor sin decirlo sería exactamente el problema que la métrica existe para
evitar.

## Dos límites del proxy que este hallazgo expone

**Está sesgado a favor de la rama vectorial.** El header contextual de cada chunk
contiene `[Documento: X - <título>]`, así que consultar por el título matchea
literalmente el header de todos los chunks de ese documento. Una métrica que
premia eso no puede juzgar con justicia si la rama léxica aporta.

**Y no mide lo que un generador necesita.** `precision@k` sobre varios documentos
relevantes —lo que hace el curso— mide si los k que entran al contexto sirven.
El proxy mide si aparece uno. Son preguntas distintas, y la segunda es la que
importa para el entregable.

Por eso la decisión de la rama léxica queda **abierta hasta el golden set**, y no
resuelta por el proxy.

## Latencia, que también es un hallazgo

El retriever agrega ~340 ms sobre una búsqueda vectorial cruda incluso con una
sola rama (402 ms contra 66 ms). Sale de dos cosas: cada rama pide 30 candidatos
en vez de 10 —para que la fusión tenga con qué trabajar— y hay una consulta de
rehidratación al final. Aceptable para un batch, discutible para un endpoint, y
hay que medirlo antes de exponerlo.

# Tareas de implementación

## 1. Las métricas primero

- [x] 1.1 `scripts/eval_retrieval_proxy.py`: acierto@1/5/10 sobre los documentos
      de título único, con `--limit` para muestrear y `--full` para los 1.871.
- [x] 1.2 El reporte del proxy declara que es un proxy y enumera sus límites.
- [x] 1.3 Registrar la línea base del vector solo, con la muestra completa.
- [x] 1.4 `evals/golden_retrieval.json`: 20-30 preguntas borradoreadas de
      secciones reales, cada una con sus documentos relevantes y con
      distractores deliberados. Marcado como PENDIENTE DE REVISIÓN.
- [x] 1.5 `scripts/eval_retrieval.py`: precision@k y latencia por configuración
      con nombre, como el `eval_retrieval_s10.py` del curso.
- [x] 1.6 Mientras el golden set no esté revisado, su reporte lo dice.

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
- [x] 4.5 precision@k sobre el golden set, por configuración: solo vector, solo
      léxico, y la fusión.
- [x] 4.6 Medir qué le hace el tope por documento a las dos métricas.
- [x] 4.7 Medir cuántos candidatos necesita cada camino para que el tope por
      documento no se quede sin con qué llenar. `branch_limit` 30 → 100.

## 5. Endpoint

- [ ] 5.1 `GET /search` con la consulta y los filtros como query params.
- [ ] 5.2 La respuesta lleva la procedencia de cada hit: documento, sección,
      breadcrumb y de qué camino vino.
- [ ] 5.3 Tests del router con la capa de retrieval mockeada.

## 6. Lo que el curso tiene y este cambio no

- [ ] 6.0 Dejar anotado en el archive: `retrieval/reranker.py`,
      `query_transform.py` y `router.py` existen en el curso y quedan afuera a
      propósito. Medir primero la fusión sola, después agregar.

      Evidencia acumulada a favor del reranker, cuatro casos medidos e
      independientes [VERIFICADO-CORPUS]:

      1. Pólizas: 8 de 14 relevantes en el top-10, 13 de 14 en el top-60.
      2. `COL502` y `COL520` en los puestos 41 y 52.
      3. El derrumbe de hit@1 cuando se fusiona el léxico sin reordenar.
      4. Las dos preguntas de siniestros que puntúan 0 en p@10 **no son
         fallas de recall**: `SI012` está en el puesto 15, `SIL00970` en el 14 y
         `SIC001` en el 18. Solo `SIC002` está genuinamente afuera del top-60.
         Tres de los cuatro documentos que "faltan" están entre los puestos 11
         y 20 — exactamente el rango que un reranker recupera.
      5. Sobre los 85 pares pregunta-documento de las 35 preguntas humanas:
         **21 son problema de rango** (puestos 11-60, los rescata) y **15 son
         problema de recall** (afuera del top-60, no los puede rescatar). Ver
         `design.md` §4c: son conjuntos disjuntos y hacen falta dos arreglos.

- [ ] 6.0b Descomposición de consulta, con la evidencia que la reactiva.
      Medida antes sobre 5 preguntas dio 1/5 → 2/5 y quedó postergada. Sobre 35:
      las **15 fallas de recall son todas de preguntas compuestas, cero en
      simples**, y **10 de los documentos que faltan en una compuesta son la
      respuesta anotada de una simple** — `CA003` sale 1º solo y no aparece en el
      top-60 de la compuesta que lo tiene anotado. El documento es recuperable;
      la consulta compuesta lo entierra.

      `window_type_name` ya viaja en cada fila y es señal utilizable: ante un
      "¿en qué pantalla?", una transacción puntual le gana a un proceso masivo.

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


## El golden set, y lo que midió

22 preguntas borradoreadas del corpus, 94 relevantes anotados, 82 distractores
deliberados, **PENDING_REVIEW**. Cada una lleva en `provenance` el criterio
verificable del que salió y dos casillas de revisión sin completar.

`precision@10` por configuración, con el techo al lado porque el número solo no
se puede leer (una pregunta con 3 relevantes y k=10 no puede pasar de 0,30):

| config | precision@10 | % del techo | distractores | ms |
|---|---:|---:|---:|---:|
| `vector` | 0,145 | 34% | 4 | 814 |
| `lexical` | 0,036 | 8% | 4 | 192 |
| `vector+exact` | 0,150 | 35% | 3 | 652 |
| `fused` | 0,132 | 31% | **2** | 776 |
| **`vector+exact` cap 1** | **0,227** | **53%** | 7 | 955 |
| `vector+exact` cap 2 | 0,195 | 46% | 6 | 595 |
| `vector+exact` cap 3 | 0,182 | 43% | 4 | 572 |
| `vector` cap 1 | 0,209 | 49% | 7 | 552 |

Y el desglose por tipo, que es lo que separa las causas:

| tipo | techo | `vector` | `vector+exact` | `v+exact` cap 1 | `vector` cap 1 |
|---|---:|---:|---:|---:|---:|
| `by_code` (6) | 0,100 | 0,033 | **0,100** | **0,100** | 0,033 |
| `declared_precedence` (10) | alto | 0,130 | 0,100 | **0,190** | **0,190** |
| `field_validations` (6) | alto | 0,283 | 0,283 | **0,417** | **0,417** |

### Tres conclusiones, cada una aislada

**1. La rama exacta es lo que resuelve `by_code`, y lo resuelve entero.** De
0,033 a 0,100, que es **el 100% del techo**. Y `vector` cap 1 —que tiene el tope
pero no la rama exacta— vuelve a 0,033: es la rama exacta y no el tope.

**2. El tope por documento es el hallazgo más grande del cambio.** De 0,150 a
0,227, del 35% al 53% del techo. La causa se ve mirando un caso: para *"qué
procesos hay que ejecutar antes de MGSL006"*, las configs sin tope devuelven
**diez chunks de MGSL006 y ninguno de los seis procesos de su cadena declarada**.
Un relevante distinto de siete.

**3. La curva del tope es monótona:** cap 1 (0,227) > cap 2 (0,195) > cap 3
(0,182) > sin tope (0,150). Y al revés con los distractores: cuanto más apretado
el tope, más documentos entran y más distractores con ellos.

### Por qué NO cambié el default a cap 1, aunque mida mejor

Porque el golden set tiene un hueco que yo mismo le hice. Las 22 preguntas salen
de criterios que naturalmente dan **varios** documentos relevantes, así que el
conjunto premia traer muchos documentos. **No hay ninguna pregunta profunda sobre
un solo documento** —del estilo *"qué pasa si el importe de ajuste supera la
comisión neta"*, cuya respuesta correcta son varios chunks de `AGL009` y de nadie
más—.

Sin ese tipo de pregunta, la métrica no puede ver lo que cap 1 rompe. Poner el
default en el valor que maximiza una métrica con ese punto ciego sería
sobreajustar al sesgo de mi propio borrador.

El tope queda expuesto como parámetro, la curva medida y documentada, y la
decisión del default es del dueño del repo con la evidencia a la vista. Agregar
4-6 preguntas profundas de un solo documento es lo más valioso que se le puede
hacer al conjunto, y quedó anotado en `how_to_review`.


## Segunda tanda del golden set: enfocada por modulo

El dueno del repo definio el foco: **polizas, siniestros, cobranzas y
disenador**. El generador pasa a estar manejado por modulo y no por el material.

30 preguntas, 130 relevantes anotados, 85 distractores:

| modulo | preguntas | relevantes |
|---|---:|---:|
| Cobranzas | 9 | 41 |
| Polizas | 7 | 27 |
| Siniestros | 7 | 32 |
| Disenador | 7 | 30 |

### Por que el primer borrador salio sesgado

Dejaba que el material eligiera: tomaba las cadenas de precedencia mas largas, y
todas viven en reaseguros. Resultado, 27% de los relevantes en un modulo de **36
documentos sobre 2211**, y 55% de tipo `process_report` cuando el corpus es
mayoritariamente `maintenance`. Siniestros, interfaces y disenador no aparecian.

### Un problema que hubo que resolver primero: con que se filtra un modulo

El `module_name` del breadcrumb resuelve para el 54% del corpus, asi que filtrar
por el se perdia **75 de los 127 documentos de siniestros y 106 de los 134 de
disenador** — justo dos de los cuatro modulos pedidos.

El modulo del corpus (el JSON en el que se troceo el documento) es la unica
agrupacion completa, y **no es una columna de `chunks`**. El generador lo lee de
los JSON. Queda anotado como hueco: la recuperacion no puede filtrar por el.

### Y un hallazgo sobre el alcance del mapa

Las cadenas de precedencia **casi no existen en estos cuatro modulos**: 2 en
cobranzas, 0 en polizas, siniestros y disenador. Las declaraciones viven en los
procesos batch de reaseguros y margen de solvencia. Se registra en
`known_gaps` en vez de rellenar con preguntas de modulos que nadie pidio.

## Los hallazgos REPLICAN en el conjunto nuevo

Que dos golden sets distintos —uno pesado en reaseguros, otro en el nucleo del
negocio— den las mismas conclusiones es la mejor senal de que no eran artefactos
del primero.

| config | precision@10 | % del techo | distractores |
|---|---:|---:|---:|
| `vector` | 0,150 | 35% | 7 |
| `lexical` | 0,030 | 7% | 3 |
| `vector+exact` | 0,167 | 39% | **3** |
| `fused` | 0,120 | 28% | 5 |
| **`vector+exact` cap 1** | **0,197** | **45%** | 9 |
| `vector+exact` cap 2 | 0,187 | 43% | 7 |
| `vector+exact` cap 3 | 0,180 | 42% | 6 |

| tipo | techo | `vector` | `vector+exact` | `v+exact` cap1 | `vector` cap1 |
|---|---:|---:|---:|---:|---:|
| `by_code` (12) | 0,100 | 0,058 | **0,100** | **0,100** | 0,067 |
| `field_validations` (16) | alto | 0,225 | 0,225 | **0,269** | **0,269** |
| `declared_precedence` (2) | alto | 0,100 | 0,100 | 0,200 | 0,200 |

**1. La rama exacta resuelve `by_code` entero, ahora sobre 12 preguntas** y no 6:
0,058 → 0,100, el 100% del techo. Y `vector` cap1, con tope pero sin rama
exacta, se queda en 0,067.

**2. La curva del tope sigue monotona** (0,197 > 0,187 > 0,180 > 0,167) y los
distractores al reves.

**3. La rama lexica sigue restando** (`fused` 0,120 contra `vector+exact` 0,167).

### Un matiz nuevo que el foco por modulo hizo visible

El beneficio del tope es **mas chico** en estos modulos (+0,030) que en el
conjunto pesado en reaseguros (+0,077). Tiene sentido: alla las preguntas de
precedencia tenian cadenas de hasta 7 documentos relevantes, donde la
concentracion en uno solo hace mas dano. El valor del tope depende del tipo de
pregunta, no es una constante del sistema.


## Preguntas reales de usuario, y lo que midieron

El dueno del repo aporto **6 preguntas reales de usuarios de cobranzas**, cada
una con el documento que la responde. Son las mas valiosas del conjunto por dos
razones: las hizo una persona, y son de **un solo documento relevante** — el tipo
que el generador automatico no podia producir porque sus criterios daban siempre
varios.

Viven en `evals/golden_curated.json`, separado del borrador, porque regenerar el
borrador las borraria. `draft_golden_set.py` las mezcla y nunca las sobreescribe.
El conjunto pasa a tener 36 preguntas y el status a `PARTIALLY_REVIEWED`: las 6
curadas estan revisadas, las 30 borradoreadas no, y un status unico tendria que
mentir sobre una de las dos mitades.

### Dos metricas nuevas, porque `precision@k` no servia para estas

Con un solo relevante, `precision@10` tiene techo 0,100 y no dice nada. Se
agregaron `encontro` (aparecio entre los 10) y `en top3` (aparecio entre los 3
primeros, que es lo que un usuario realmente lee).

| config | p@10 | encontro | en top3 | distr | ms |
|---|---:|---:|---:|---:|---:|
| `vector` | 0,136 | 78% | 67% | 7 | 634 |
| `lexical` | 0,033 | 28% | 11% | 3 | 272 |
| `vector+exact` | 0,150 | **92%** | **86%** | **3** | 514 |
| `fused` | 0,111 | 86% | 75% | 5 | 810 |
| `vector+exact` cap1 | **0,175** | **92%** | **86%** | 9 | 521 |

`encontro 92% / en top3 86%` se lee sin explicacion, que es mas de lo que se
puede decir de `precision@10 = 0,150`.

### 4 de las 6 en el puesto 1

Con `vector` y con `vector+exact`, cuatro preguntas devuelven su documento
**primero**: COL005, COL003, COL001 y CO501.

Y la rama lexica vuelve a restar, ahora de forma visible: con `fused`, tres de
esas cuatro **bajan del puesto 1 al 2**.

### Las dos que falla, y por que — el mejor argumento para el reranker

`COL502` y `COL520` no aparecen en el top-10. Pero **no es que no se encuentren**:

| pregunta | documento | puesto real |
|---|---|---:|
| deposito PAC menor por comision del banco | `COL502` | **41** |
| totales de un lote antes del cobro | `COL520` | **52** |

Y los terminos estan en el texto: `PAC` en 39 chunks de COL502 y 73 de COL520,
`banco` en 13, `deposito` en 6, y `anulada`/`rechazada`/`lote`/`solicitada` en 2-3
chunks de COL520.

En COL502 se ve el mecanismo del fallo: la consulta dice "comision" y la
similitud lleva a `PRODUCERS_AGL009`, que es sobre comision de **productores**, no
comision **bancaria**. La palabra secuestro la consulta.

Verificado que con un conjunto candidato mas ancho (`branch_limit` 80 en vez de
30) **los dos entran al candidato**, en los puestos 41 y 52.

Eso es la tercera evidencia independiente de que **falta el reranker**, y la mas
concreta: el trabajo de la fusion es meter la respuesta en el conjunto candidato
—y lo hace— y el de subirla arriba es del reranker. Ensanchar el candidato sin
reranker no sirve: el puesto 41 sigue sin ser un top-10.

**Los dos van juntos:** ensanchar el candidato es el prerequisito del reranker,
no una mejora por si sola.


## Preguntas compuestas: el hallazgo mas fuerte, y el que cambio las prioridades

El dueno del repo aporto 5 preguntas mas de cobranzas, **compuestas**: cada una
tiene tres sub-preguntas y necesita entre 3 y 5 documentos, con la justificacion
de por que cada uno hace falta. El conjunto queda en 41 preguntas, 11 de ellas
escritas por una persona.

Esto es exactamente el modo de falla que el golden set del curso nombra primero
—*"averaged multi-topic queries"*— y el que ningun criterio automatico podia
generar.

### La recuperacion falla en la mitad

| pregunta | requeridos | sin tope | cap 1 |
|---|---:|---:|---:|
| lote PAC y rechazos | 4 | 2/4 | **4/4** |
| rechazo y cuenta corriente | 3 | 1/3 | 1/3 |
| cartera de pendientes | 3 | 1/3 | 1/3 |
| desmarcar y repaso | 3 | 1/3 | 2/3 |
| financiamiento por cuotas | 5 | 1/5 | 1/5 |
| **TOTAL** | **18** | **6/18** | **9/18** |

Una sola consulta que promedia tres temas cae "entre" los tres y recupera
documentos cercanos a ese promedio, que suelen no ser ninguno de los tres.

### La descomposicion NO lo arregla, y lo verifique antes de recomendarla

La hipotesis obvia es partir la pregunta compuesta en sus sub-preguntas y unir
por round-robin —que es para lo que el curso tiene `round_robin_merge()` al lado
de RRF: cuando las sub-consultas cubren temas distintos, importa la **cobertura**
y no el **acuerdo**—.

Probado a mano sobre la peor pregunta: **1/5 pasa a 2/5**. Mucho menos de lo
esperado.

La razon se ve mirando un caso: `COL704` se titula *"Parametros para la carga
automatica"*. Nada en su texto la conecta con "rechazos de cuotas de
financiamiento". Esa relacion no esta en el texto de ningun documento — esta
**entre** los documentos.

Si hubiera recomendado descomposicion sin medirla, habria vendido una mejora de
1/5 a 2/5 como si fuera la solucion.

### Lo que SI lo arregla: expandir por el mapa de procesos

El mapa conecta esos nueve documentos con 14 aristas. Y `COL500` —que la busqueda
**si** encuentra— es requerido por `CO501`, `COL502`, `COL520` y `COL704`: los
cuatro que faltaban.

Medido, expandiendo desde los documentos recuperados por las aristas `requires` y
`references`:

| pregunta | sin expansion | con expansion |
|---|---:|---:|
| lote PAC y rechazos | 4/4 | 4/4 |
| rechazo y cuenta corriente | 1/3 | **2/3** |
| cartera de pendientes | 1/3 | 1/3 |
| desmarcar y repaso | 2/3 | 2/3 |
| financiamiento por cuotas | 1/5 | **5/5** |
| **TOTAL** | **9/18** | **14/18** |

**De 50% a 78% de cobertura**, y la peor pregunta pasa de 1/5 a 5/5.

Es el pago de haber construido el mapa antes de la recuperacion, que era
exactamente el argumento de ese orden.

## Las prioridades, ahora medidas y no supuestas

1. **Expandir por el mapa** — 9/18 a 14/18 medido. El mayor salto disponible, y
   el mapa y su tabla `process_map_edges` indexada en las dos puntas ya existen.
2. **Reranker** — para `COL502` y `COL520`, que estan en los puestos 41 y 52. La
   fusion las mete en el candidato y no las sube.
3. **Descomposicion de consulta** — medida en 1/5 a 2/5. Mucho mas abajo de lo
   que habria supuesto sin medir.

Dos preguntas no mejoran con expansion (`cartera de pendientes` y
`desmarcar y repaso`): les falta `COL007` y `COL001`, que no tienen aristas hacia
los documentos que si se recuperan. La expansion tampoco es una bala de plata.


## Preguntas de polizas: cada modulo necesita algo distinto

El dueno del repo aporto 6 preguntas mas, de polizas: 3 de un solo documento y 3
compuestas. El conjunto de curadas queda en 17 (9 simples + 8 compuestas), 41
relevantes anotados, y el conjunto total en 47 preguntas.

### Un hallazgo de anotacion antes de medir

Tres anotaciones decian `ca001.md`. Ese archivo declara **un solo id en su linea
3, `CA001k`**, y `CA001` **no esta declarado como id en ningun archivo del
corpus**: el nombre del archivo y el id de la transaccion no coinciden en el
export. El chunker hace lo correcto al confiar en la linea de id y no en el
nombre del archivo. Se anoto `CA001k`, con la nota en `provenance` y en
`known_annotation_notes`.

### Las 3 simples: perfectas

`CA051`, `CAL006` y `CA022` vuelven **1/1** cada una. Preguntas especificas
—un codigo de error, una formula, una validacion— con un documento cada una: el
caso que la recuperacion ya resuelve.

### Las 3 compuestas, y el contraste con cobranzas

| | sin expansion | con expansion del mapa |
|---|---:|---:|
| compuestas de cobranzas | 9/18 | **14/18** |
| compuestas de polizas | 8/14 | **8/14** (sin cambio) |

La expansion no aporta **nada** en polizas. La razon, medida: hay **0 aristas**
entre los documentos de polizas del golden set, contra **14** entre los de
cobranzas.

Y eso conecta con un hallazgo anterior: las aristas `requires` viven en los
procesos batch, y polizas es mayormente pantallas ABM que no declaran
precedencia. La densidad del grafo no es uniforme, asi que **el valor de la
expansion depende del modulo**.

### Lo que polizas SI necesita

Ensanchando el conjunto de resultados de 10 a 60:

| | top 10 | top 60 |
|---|---:|---:|
| movimientos en policy_his | 2/4 | **4/4** |
| propuesta a poliza | 4/5 | **5/5** |
| primera prima y caja | 2/5 | **4/5** |
| **TOTAL** | **8/14** | **13/14** |

Los documentos **estan** en el candidato, abajo del puesto 10. Lo que falta ahi
no es encontrarlos: es **ordenarlos**.

## Las prioridades, corregidas

La tanda de cobranzas me habia hecho poner la expansion primero. Polizas dice
que el reranker es al menos igual de importante, y que **cada mecanismo arregla
un problema distinto**:

1. **Reranker sobre un candidato mas ancho** — polizas: 8/14 disponibles a top-10
   pasan a 13/14 a top-60. Tambien es lo que sube `COL502` y `COL520` desde los
   puestos 41 y 52.
2. **Expansion por el mapa** — cobranzas: 9/18 a 14/18. Solo sirve donde el grafo
   es denso, que son los procesos batch.
3. **Descomposicion de consulta** — medida en 1/5 a 2/5. Sigue ultima.

Los dos primeros son complementarios y no alternativos: el reranker ordena lo que
ya se recupero, la expansion trae lo que no se recupero pero esta declarado como
relacionado.

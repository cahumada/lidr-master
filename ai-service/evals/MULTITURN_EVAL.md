# Evaluación multi-turno — las dos direcciones del resolver

Mide el resolver de preguntas referenciales de `conversation-memory`: la pieza
que convierte «¿y qué validaciones tiene?» en una pregunta buscable antes de
que corra la recuperación.

## Por qué existe este archivo

El resolver estaba medido **en una sola dirección**, y su propio `design.md` lo
declaraba: se sabía que no reescribe una pregunta que nombra su propio sujeto
—el falso positivo— y no se sabía con qué frecuencia deja sin resolver una que
sí tenía referente.

Esa asimetría lo favorece. Un resolver que **no reescribe nunca** saca cero en
falsos positivos, así que ese número solo no distingue un resolver conservador
de uno roto. El par es lo único que dice algo:

| dirección | qué es | qué la premia si se reporta sola |
|---|---|---|
| falso **negativo** | había referente y no lo resolvió | un resolver que dispara con todo |
| falso **positivo** | no había, y lo reescribió igual | un resolver que no dispara nunca |

## El conjunto

`golden_multiturn.json`: **12 secuencias, 25 turnos**. De los 25, doce son
primeros turnos y no puntúan —no hay turno anterior del que depender—. Los 13
restantes llevan la anotación que hace todo el trabajo:

| etiqueta | cuántas | qué significa | qué es una falla |
|---|---:|---|---|
| `clear` | 8 | una persona que leyó el turno anterior sabe de qué habla; la pregunta sola no lo dice | no reescribirla |
| `absent` | 3 | se sostiene sola: nombra su transacción, o su sujeto en palabras | reescribirla |
| `ambiguous` | 2 | hay más de un referente defendible, o el referente es la respuesta anterior y no un documento | ninguna: se reporta aparte |

Los `ambiguous` **no se cuentan de ningún lado**. Contarlos exigiría elegir una
de las lecturas y después evaluar al resolver contra la propia elección.

Dos campos que se parecen y no son lo mismo:

- **`expected_referents`** — hacia dónde apunta la pregunta.
- **`relevant_document_ids`** — qué documento la responde.

En `MT-CA014-matriz` («¿Y para la póliza matriz?») el referente es `CA014`
—es lo que el usuario venía leyendo— y el documento que responde es `CA014A`.
Un resolver que nombra bien el referente y una recuperación que trae el
documento equivocado son **dos fallas distintas**, y colapsarlas en un número
deja sin saber cuál pasó.

## Cómo se mide

```bash
uv run python scripts/eval_multiturn.py                  # modo resolver
uv run python scripts/eval_multiturn.py --through-graph  # por los endpoints
```

**Modo `resolver`** (el default): camina cada secuencia y llama a `resolve()`
directo. Los hechos que recibe el turno N se arman desde los documentos
**anotados** del turno N-1, no desde lo que la recuperación devolvió de verdad.
Esa es la aislación que hace que el número signifique algo: un falso negativo
acá es el resolver fallando **sobre un turno anterior perfecto**, no la
recuperación habiendo perdido el referente antes. Sin base, sin LLM, sin
servidor: corre en un segundo.

**Modo `--through-graph`**: corre las mismas secuencias por los endpoints
reales —`POST /answer/session` → `POST /answer/agentic/start` → sondeo de
`GET /answer/agentic/{id}/progress`— con el `TestClient` de FastAPI sobre la app
de verdad. Pasa por los routers, los modelos y las dependencias reales
—incluido el guard del token— sin necesitar un proceso arriba. Agrega lo que el
modo resolver no puede ver: qué anchors quedaron en vigor, si la memoria
desplazó evidencia (`dropped_hits`) y qué documentos se citaron. Necesita
Postgres alcanzable y gasta completions.

Los dos modos no son redundantes: el primero mide **una** pieza con entradas
ideales, el segundo mide el camino completo y **no puede** separar una falla del
resolver de una de la recuperación. Reportar solo el segundo esconde qué
arreglar.

Una corrida que pausa en el gate de revisión humana **no se retoma**. Que el
gate dispare es un resultado legítimo, y aprobarlo desde el script metería el
criterio del script en un número que mide el del sistema.

## La calidad de una reescritura, en tres pasos

«Reescribió» y «reescribió bien» son afirmaciones distintas, y este cambio
existe para dejar de reportar la primera como si fuera la segunda:

| veredicto | qué pasó |
|---|---|
| `ok` | todos los referentes que nombró estaban anotados |
| `partial_referent` | nombró el correcto **y además** otro que no era |
| `wrong_referent` | nombró solo referentes que no eran |
| `false_negative` | había referente claro y no reescribió |
| `false_positive` | no había, y reescribió |

`false_negative` y `wrong_referent` **nunca comparten columna**. El primero es
el resolver callándose; el segundo es hablando y apuntando a otro lado, que es
peor: produce una búsqueda equivocada con más confianza que la pregunta rota,
porque ahora parece bien formada.

## Lo que se ve al comparar los dos modos

Las dos direcciones dan lo mismo en los dos modos —falso negativo **50%**
(4 de 8), falso positivo **33%** (1 de 3)—, y era esperable: el resolver decide
con un regex sobre el texto de la pregunta, y ese texto no cambia porque haya
una base atrás.

Lo que **sí** cambia es la calidad de lo que reescribe, y ahí está el hallazgo:

| | modo resolver | por el grafo |
|---|---:|---:|
| reescrituras correctas | **4/4** | **0/4** |
| reescrituras parciales | 0/4 | **4/4** |

Aislado, cada reescritura nombra exactamente el referente anotado. Por el
grafo, **las cuatro** nombran uno de más. La causa no es el resolver sino lo
que recibe: el turno anterior citó **diez** documentos, `last_document_ids` los
guarda todos, y el resolver nombra los primeros `MAX_REFERENTS = 2`. Así,
`¿Y qué validaciones tiene?` se busca como `(sobre CA014, CAC1021)` cuando el
usuario preguntaba por uno solo.

Eso no se podía ver antes de este eval y no se puede ver en el modo aislado. Es
el argumento para tener los dos: el modo resolver dice que la regla de
sustitución está bien, el modo grafo dice que la fuente de referentes no lo
está. Arreglarlo es una decisión sobre `facts_from_turn` o sobre
`MAX_REFERENTS`, no sobre el regex — y es un cambio aparte, con esta medición
como línea de base.

**El costo del falso negativo es peor de lo que sugiere «no reescribió».** Una
pregunta sin resolver no se queda sin respuesta: se busca tal cual y trae
ruido. `¿Qué campos tiene?` devolvió `HO001, MGE001, INT54550…`, ninguno
relacionado con el `CO008` del turno anterior; `¿Qué pasa si no la completo?`
devolvió `MA0278, MCA005, CA050…` en lugar de `CA001M`. El sintetizador después
escribe una respuesta bien citada sobre eso, que es exactamente el riesgo que
el docstring del resolver describe —una respuesta equivocada que llega con
procedencia verificable— pero llegando por la otra puerta.

**Los anchors sí quedan en vigor.** `MT-anchor-prefijo-fijado` es la única
secuencia con anchor, y el modo grafo la reporta con `transaction_prefix` en
vigor: su turno 2 no nombra el prefijo y devolvió diez documentos `CA*`, contra
el `CO510, BC968, MCO505…` que devolvió la misma pregunta sin anchor en
`MT-CA014-posesivo`.

**`dropped_hits` fue 0 en los 13 turnos**, así que estas secuencias **no
ejercitaron** el presupuesto compartido entre memoria y evidencia. No es que la
memoria nunca desplace evidencia: es que con dos o tres turnos cortos nunca
tuvo que elegir. Medir eso pide secuencias más largas, y no están acá.

## Lo que estos números NO dicen

**No son una estimación de la tasa real de falso negativo del resolver, y el
sesgo va en una dirección conocida.** Las preguntas son elisiones naturales del
español —un posesivo, un sujeto omitido, un demostrativo, un pronombre de
objeto—, pero **cuáles de ellas entraron al conjunto se decidió después de
probar el resolver**. O sea que el 50% no dice «el resolver falla en la mitad de
las preguntas referenciales que un usuario escribe»; dice «hay al menos cuatro
formas corrientes de elidir el sujeto que el resolver no marca, y en este
conjunto son la mitad». Lo que el número sirve para hacer es **fijar un antes**:
si un cambio en el resolver baja el falso negativo sin subir el falso positivo,
eso es una mejora medida sobre los mismos casos.

**No hay conversaciones reales detrás.** El corpus tiene preguntas reales de
usuario —están en `golden_curated.json`— pero no hay registro de sesiones
multi-turno de las que sacar segundos turnos auténticos. Los 13 turnos
posteriores los escribió quien armó el archivo. Es la misma reserva que
`COMO_LEER.md` deja sobre el golden de recuperación, un grado más fuerte:
allá al menos las anotaciones salían de criterios verificables del corpus, y
acá la anotación que decide cada veredicto es un juicio.

**El conjunto es chico y cada número se mueve mucho.** El falso negativo es
4 de 8 y el falso positivo 1 de 3: reetiquetar **una** secuencia mueve el
primero 12 puntos y el segundo 33. Sirven para comparar el resolver contra sí
mismo antes y después de un cambio, no para publicarlos como la precisión del
sistema.

**No miden si la respuesta fue buena.** Miden si la pregunta con la que se
buscó era la correcta. Que un turno resuelva bien su referente y que el
sintetizador conteste bien son dos cosas, y la segunda la mide
[`GENERATION_EVAL.md`](GENERATION_EVAL.md).

**El modo grafo no separa culpas.** Cuando un turno no cita el documento
esperado, la tabla del grafo no dice si falló el resolver, la recuperación, el
presupuesto de contexto o el rerank. Para eso está el modo resolver, que aísla
una sola pieza. Los dos juntos ubican la falla; ninguno solo lo hace.

## Resultados — modo resolver

Corrida: modo `resolver`, 11 turnos puntuados (8 `clear`, 3 `absent`) y 2 `ambiguous` fuera de la métrica.

**SIN REVISAR.** El golden set está en `DRAFT_NOT_REVIEWED`: 12 de 12 secuencias tienen alguna casilla de `review` sin confirmar. La anotación que decide cada veredicto es **el juicio humano de si una pregunta depende de la anterior**, así que hasta que alguien la confirme estos números miden el criterio de quien escribió el archivo.

| métrica | valor | qué mide |
|---|---:|---|
| `false_negative_rate` | 50% | de las preguntas con referente claro, cuántas quedaron sin resolver |
| `false_positive_rate` | 33% | de las que se sostenían solas, cuántas fueron reescritas igual |
| reescrituras correctas | 4/4 | de las que reescribió, cuántas nombraron solo el referente anotado |
| reescrituras parciales | 0/4 | nombró el referente correcto y además otro |
| reescrituras erradas | 0/4 | nombró un referente que no era |
| `ambiguous` reescritas | 1/2 | informativo: no cuenta ni a favor ni en contra |

### Por turno

| secuencia | turno | pregunta | referente | reescribió | nombró | veredicto |
|---|---:|---|---|---|---|---|
| `MT-CA014-validaciones` | 2 | ¿Y qué validaciones tiene? | clear | sí | CA014 | ok |
| `MT-CA014-posesivo` | 2 | ¿Cuáles son sus validaciones? | clear | no | — | false_negative |
| `MT-CO008-campos` | 2 | ¿Qué campos tiene? | clear | no | — | false_negative |
| `MT-OP001-esa-pantalla` | 2 | ¿Qué validaciones tiene esa pantalla? | clear | no | — | false_negative |
| `MT-CA014-matriz` | 2 | ¿Y para la póliza matriz? | clear | sí | CA014 | ok |
| `MT-OP004-autonoma` | 2 | ¿Cómo se actualizan las cuentas bancarias en OP004? | absent | no | — | ok |
| `MT-SI004-autonoma-sin-codigo` | 2 | ¿Qué validaciones existen sobre el campo Cliente en el ingreso de pagos? | absent | no | — | ok |
| `MT-clave-ambiguo` | 2 | ¿Y eso quién lo autoriza? | ambiguous | sí | CA001k, CA001M | unscored |
| `MT-OP001-reemplazo-de-referente` | 2 | ¿Y cómo se actualizan las cuentas bancarias y de caja? | absent | sí | OP001 | false_positive |
| `MT-OP001-reemplazo-de-referente` | 3 | ¿Y qué validaciones tiene? | clear | sí | OP004 | ok |
| `MT-CA001M-clave-incompleta` | 2 | ¿Qué pasa si no la completo? | clear | no | — | false_negative |
| `MT-CO001-meta-pregunta` | 2 | ¿Me lo explicás con un ejemplo? | ambiguous | no | — | unscored |
| `MT-anchor-prefijo-fijado` | 2 | ¿Y qué validaciones tiene? | clear | sí | CA014 | ok |

## Resultados — por el grafo

Corrida: modo `through-graph`, 11 turnos puntuados (8 `clear`, 3 `absent`) y 2 `ambiguous` fuera de la métrica.

**SIN REVISAR.** El golden set está en `DRAFT_NOT_REVIEWED`: 12 de 12 secuencias tienen alguna casilla de `review` sin confirmar. La anotación que decide cada veredicto es **el juicio humano de si una pregunta depende de la anterior**, así que hasta que alguien la confirme estos números miden el criterio de quien escribió el archivo.

| métrica | valor | qué mide |
|---|---:|---|
| `false_negative_rate` | 50% | de las preguntas con referente claro, cuántas quedaron sin resolver |
| `false_positive_rate` | 33% | de las que se sostenían solas, cuántas fueron reescritas igual |
| reescrituras correctas | 0/4 | de las que reescribió, cuántas nombraron solo el referente anotado |
| reescrituras parciales | 4/4 | nombró el referente correcto y además otro |
| reescrituras erradas | 0/4 | nombró un referente que no era |
| `ambiguous` reescritas | 1/2 | informativo: no cuenta ni a favor ni en contra |

### Por turno

| secuencia | turno | pregunta | referente | reescribió | nombró | veredicto |
|---|---:|---|---|---|---|---|
| `MT-CA014-validaciones` | 2 | ¿Y qué validaciones tiene? | clear | sí | CA014, CAC1021 | partial_referent |
| `MT-CA014-posesivo` | 2 | ¿Cuáles son sus validaciones? | clear | no | — | false_negative |
| `MT-CO008-campos` | 2 | ¿Qué campos tiene? | clear | no | — | false_negative |
| `MT-OP001-esa-pantalla` | 2 | ¿Qué validaciones tiene esa pantalla? | clear | no | — | false_negative |
| `MT-CA014-matriz` | 2 | ¿Y para la póliza matriz? | clear | sí | CA014, POLICIES_INDEX | partial_referent |
| `MT-OP004-autonoma` | 2 | ¿Cómo se actualizan las cuentas bancarias en OP004? | absent | no | — | ok |
| `MT-SI004-autonoma-sin-codigo` | 2 | ¿Qué validaciones existen sobre el campo Cliente en el ingreso de pagos? | absent | no | — | ok |
| `MT-clave-ambiguo` | 2 | ¿Y eso quién lo autoriza? | ambiguous | sí | CA001k, MA0017 | unscored |
| `MT-OP001-reemplazo-de-referente` | 2 | ¿Y cómo se actualizan las cuentas bancarias y de caja? | absent | sí | OP001, CASH_AND_BANKS_INDEX | false_positive |
| `MT-OP001-reemplazo-de-referente` | 3 | ¿Y qué validaciones tiene? | clear | sí | CASH_AND_BANKS_INDEX, OP004 | partial_referent |
| `MT-CA001M-clave-incompleta` | 2 | ¿Qué pasa si no la completo? | clear | no | — | false_negative |
| `MT-CO001-meta-pregunta` | 2 | ¿Me lo explicás con un ejemplo? | ambiguous | no | — | unscored |
| `MT-anchor-prefijo-fijado` | 2 | ¿Y qué validaciones tiene? | clear | sí | CA014, CA013 | partial_referent |

### Lo que agregó el grafo

| secuencia | turno | estado | citó | anchors | `dropped_hits` |
|---|---:|---|---|---|---:|
| `MT-CA014-validaciones` | 2 | completed | CA014, CAC1021, CO510, BC967, BC968, CA006, CAC1005A, CAC1005B, CAC1005, CAC936 | — | 0 |
| `MT-CA014-posesivo` | 2 | completed | CO510, BC968, MCO505, OS001, BC967, MGI1401_K, BC001N, CRL892, AGL854, CAL036 | — | 0 |
| `MT-CO008-campos` | 2 | completed | HO001, MGE001, INT54550, INT54549, INT54544, INT54559, GIL54060, GIL54056, GIL54061, GIL54057 | — | 0 |
| `MT-OP001-esa-pantalla` | 2 | completed | MGI1401_K, MGI1406, CO513, DP042, MCA400, DP038, CA008, SG002, GI1402, AM006 | — | 0 |
| `MT-CA014-matriz` | 2 | completed | CA014, POLICIES_INDEX, CA014A, CAL013, CA022, VI666, AM003, CA016A, CA022A, CA034 | — | 0 |
| `MT-OP004-autonoma` | 2 | completed | OP004, CASH_AND_BANKS_INDEX, OP010_k, OP502, OP001, OPL003, OP002, OP092, OP503, AGL002 | — | 0 |
| `MT-SI004-autonoma-sin-codigo` | 2 | completed | CO008, CO010, MCO505, OP502, CO700_k, OPC015_k, AG001, OPC010_K, CO685, CA023 | — | 0 |
| `MT-clave-ambiguo` | 2 | completed | CA001k, MA0017, MNC500, BC015, CO722, CA001M, CA001A, CA004, CA401, COL723 | — | 0 |
| `MT-OP001-reemplazo-de-referente` | 2 | completed | CASH_AND_BANKS_INDEX, OP004, OP001, OP502, OP002, CO001_A, OPL003, OP010, OP010_k, DOCUMENTS_INDEX | — | 0 |
| `MT-OP001-reemplazo-de-referente` | 3 | completed | OP004, MCO782, OP002, MCO741, MS7000, MCO505, BC968, MS003, OP502, OP001 | — | 0 |
| `MT-CA001M-clave-incompleta` | 2 | completed | MA0278, MCA005, CA050, SI050, MA0135, POLICIES_GENERAL, MA0181, SIL001, SIL009, SIL500 | — | 0 |
| `MT-CO001-meta-pregunta` | 2 | completed | DP08B2, DP008, CAC1005, CAC1005A, CAC1005B, CAC1006, CAC1021, CAC1023, CAC1024, CAC950 | — | 0 |
| `MT-anchor-prefijo-fijado` | 2 | completed | CA014, CA013, CA006, CA051, CA659, CA500, CA035, CA028, CA403, CA001k | transaction_prefix | 0 |

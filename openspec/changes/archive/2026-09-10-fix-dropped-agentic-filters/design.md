# Diseño

## 1. Honrarlos, no rechazarlos

Ante un campo que se acepta y se ignora hay dos salidas legítimas, y el repo ya
usó la otra: `POST /answer` **rechaza** `session_id` con 422 en lugar de
responder sin memoria, porque no tiene planner que resuelva una pregunta
referencial y aceptar el campo sería prometer algo que no puede dar.

Acá la situación es la inversa. El grafo **sí** puede filtrar —el
`evidence_retriever` ya arma `SearchFilters` y el retriever es el mismo que usa
`/search`—, la consola ya tiene los dos selectores construidos y poblados desde
`/api/search/facets`, y `POST /answer` los honra con el mismo contrato. Rechazar
con 422 rompería la pantalla y obligaría a sacar controles que el operador
espera usar.

Así que se honran. El 422 queda descartado como salida.

## 2. Precedencia: request → pregunta → anchor

Hay tres fuentes de filtros y hasta ahora solo se resolvía el conflicto entre
dos. `_apply_anchors` ya escribió la regla:

> *"A filter the question itself names wins: pinning «module CA» should not stop
> somebody from asking about DF explicitly in one turn. The anchor is a default,
> not a cage."*

Esta decisión **no la invierte**: le agrega un nivel arriba.

| fuente | qué es | precedencia |
|---|---|---|
| `request` | el operador eligió esto para este turno, en un control que existe para recortar | **gana** |
| pregunta | una heurística que extrajo un código con forma de transacción del texto | media |
| anchor | un default fijado en un turno anterior | pierde |

El razonamiento: de las tres, la del medio es la única que **no** es una
declaración de intención — es una inferencia sobre prosa
(`_TRANSACTION_PREFIX` sobre los tokens de la pregunta). Que un control
explícito le gane a una inferencia es la misma jerarquía que el resto del
servicio ya aplica cuando prefiere un valor declarado sobre una heurística: el
tipo de ventana declarado por `NWINDOWTY` le gana a la heurística de hijos, y el
`NG_IDENTI` declarado le gana a adivinar por nombre.

**Alternativa descartada — unir las tres.** Para `module_code`, que es una
lista, unir amplía en lugar de recortar: el operador que elige `CA` en el
selector y menciona `DF` en la pregunta recibiría resultados de los dos, que es
lo contrario de lo que un filtro significa. Un filtro que amplía no es un
filtro.

**Alternativa descartada — que el request gane también sobre el anchor pero la
pregunta no.** Sería más simple de implementar y produce un orden difícil de
explicar: el anchor perdería contra la prosa pero no contra el selector, sin una
razón que se pueda decir en una frase.

## 3. Un solo lugar resuelve, y queda anotado de dónde salió cada valor

La resolución vive en el `query_planner` y no repartida entre `initial_state` y
el retriever. `initial_state` **siembra** lo que vino del request; el planner
**resuelve**. Dos razones:

- El retriever no debe conocer la política: hoy lee `state["filters"]` y punto,
  y esa simplicidad es lo que permite que `search_corpus` sea el mismo camino
  que `/search`.
- El planner es el nodo que ya tiene las tres fuentes a la vista y el que ya
  escribe su decisión en `agent_contributions`.

Y lo que se aplica **se reporta con su origen**, como los perfiles reportan
`profile` / `settings` / `unsupported`. No es decoración: la spec de
`conversation-memory` fija que *"un filtro aplicado sin decirlo es un defecto,
no una comodidad"*, y con tres fuentes posibles, saber que se filtró no alcanza
—hay que poder ver por qué.

## 4. Por qué esto no se detectó antes

Vale dejarlo escrito, porque la causa es reproducible.

Ningún test cubría la combinación, y **el síntoma es invisible**: filtrar de
menos devuelve *más* resultados, y más resultados se leen como una búsqueda que
funcionó. El caso que lo destapó fue al revés: alguien esperaba **cero** hits de
un filtro imposible (`module_code=["ZZZ"]`) y recibió cinco.

De ahí sale un test que el change agrega y que no es el obvio: un filtro que no
matchea nada **debe** producir cero hits. Un test que solo verifique "filtrar
devuelve resultados del módulo pedido" pasa igual con el bug, porque la
heurística del planner suele coincidir con lo que el usuario eligió.

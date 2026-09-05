# Design — ejemplo trabajado en la pantalla de flujo

## El problema, en una frase

La pantalla dice **qué es** cada nodo y no dice **qué hace con una
pregunta**. Un lector que no escribió el grafo no puede reconstruir la
secuencia leyendo seis definiciones y once aristas sueltas.

## Dónde vive el ejemplo

En `app/domain/graph/catalog.py`, junto al `AgentSpec` que ya declara
rol y explicación, y viaja por `GET /config` como el resto.

La alternativa era escribirlo en la consola, donde se rendea. Perdió por
la misma razón que está escrita en el docstring del catálogo: el curso
declara el catálogo dos veces —el grafo en Python y `Agents::GraphFlow::
NODES` en Rails— y eso es lo que les permite divergir. Un ejemplo del
`query_planner` escrito en TypeScript envejecería el día que cambie
`decompose()`, sin que nada avise.

## Qué pregunta

`U-multi-lote-pac-rechazos`, de `evals/golden_curated.json`:

> Si un lote de cobranza PAC tiene problemas de pago, ¿cómo se originan
> esos boletines en el sistema, cómo puedo registrar sus rechazos
> (manual o automáticamente) y en qué pantalla valido el monto neto que
> realmente se va a notificar como cobrado?

Tres razones, en orden de peso:

1. **Es real.** La escribió un usuario y la anotó alguien que conoce el
   negocio; el archivo dice explícitamente que ese es su valor. Un
   ejemplo inventado en la pantalla sería la única prosa de la consola
   que no sale de un dato.
2. **Es compuesta.** Se parte en tres subconsultas, así que el
   `query_planner` deja de ser un nodo que «no hace nada visible» y el
   `evidence_retriever` muestra por qué corre `search_corpus` más de una
   vez.
3. **Tiene sus documentos anotados con el motivo de cada uno** (COL500,
   CO501, COL704, COL520). El ejemplo de recuperación no necesita
   inventar ids: usa los que una persona anotó, y dice que son los
   anotados, no los que el pipeline devolvió hoy.

## Qué se afirma y qué se marca como ilustrativo

Es la decisión central del change, porque un ejemplo es prosa que se
lee como un hecho.

| Nodo | Ejemplo | Estado |
|---|---|---|
| `query_planner` | 3 subconsultas + `filters={}` | **Afirmado y testeado**: sale de `decompose()` y `_suggest_filters()` corridos sobre la pregunta |
| `orchestrator` | `goto` de cada paso | **Afirmado**: la escalera y las precondiciones son deterministas y están en `orchestrator.py` |
| `citation_validator` | `grounded=True`, `confidence=0.9` | **Afirmado**: `_confidence_score(grounded=True, hit_count>=3)` es exactamente 0.9 |
| `answer_review_gate` | no pausa | **Afirmado**: `review_reasons()` es función pura y 0.9 ≥ 0.6 (el umbral default) |
| `evidence_retriever` | los 4 documentos anotados | **Ilustrativo, con fuente**: son los anotados en el golden, no los que devolvió una corrida |
| `answer_synthesizer` | un párrafo citado | **Ilustrativo**: único nodo LLM-driven; su salida cambia con modelo y persona |

El test de drift cubre la primera fila. Las dos últimas la pantalla las
marca como ejemplo ilustrativo — no hay forma de testear «el modelo
escribiría esto» y fingir que la hay sería peor que no dar el ejemplo.

## El diagrama

Once líneas `origen → destino` no muestran que el grafo es un hub. Pero
la consola tampoco puede dibujar un hub *hardcodeado*: sería volver a
declarar la topología en TypeScript.

Se **deriva** de `flow.edges`:

- hub = el nodo de `kind: "supervisor"` que es origen de dos o más
  aristas;
- radios = destinos del hub que tienen arista de vuelta al hub;
- terminal = destino del hub sin arista de vuelta (el gate);
- y `START` / `END` se toman de las aristas que los nombran.

Si esa derivación no cierra —porque el grafo dejó de ser un hub— la
pantalla cae a la lista plana de aristas que ya tenía. Degradar a algo
correcto y feo es preferible a dibujar una topología que el servicio no
declaró; es la misma regla que ya cumple el caso «servicio caído».

## Orden de los nodos

Hoy es el del catálogo. Pasa a ser el de ejecución: orquestador
primero, después `flow.ladder` (que ya viene del orquestador), y el gate
al final. `ladder` es un dato servido, no un orden escrito en la
consola, así que la numeración no inventa nada. Los nodos que no estén
en la escalera se agregan al final, para que un nodo nuevo aparezca en
la pantalla aunque nadie toque el orden.

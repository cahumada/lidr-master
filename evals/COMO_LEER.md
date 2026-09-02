# Cómo leer la evaluación de recuperación

Los números de `RETRIEVAL_EVAL.md` usan vocabulario de recuperación de
información. Acá está cada término explicado sobre **una pregunta real** del
golden set, para que no haya que creerle nada a la definición.

## La pregunta de ejemplo

> **¿Qué validaciones existen sobre el campo Código en Pólizas?**

Anotada con 6 documentos relevantes: `CA022`, `CA024`, `CA025`, `CA028`,
`CA659`, `CA727`.

Esos 6 no los eligió nadie a dedo: son los documentos de Pólizas que tienen un
chunk de `Validaciones` cuyo `metadata.field` es exactamente `Código`. Eso está
escrito en el campo `provenance` de la pregunta, y es lo que hace la anotación
**verificable** — se puede volver a correr la consulta y comprobar que son esos.

---

## Los términos de la medición

### `relevantes`

Los documentos que **deberían** aparecer en la respuesta. En el ejemplo, 6.

### `k`

Cuántos resultados se le piden al buscador. Acá siempre **k = 10**, y el sufijo
`@10` significa "mirando los primeros 10".

### `precision@k`

**De los k que devolvió, qué fracción son relevantes.**

Lo que realmente devolvió el buscador para esa pregunta:

```
sin tope                            con tope de 1 por documento
 1. GE010                            1. GE010
 2. VI021                            2. VI021
 3. CAC1016A                         3. CAC1016A
 4. CAC1016B                         4. CAC1016B
 5. CAC1016                          5. CAC1016
 6. GIL54528                         6. GIL54528
 7. GE010                            7. CA028      <- relevante
 8. CA028      <- relevante          8. CO501
 9. CO501                            9. INT54528
10. INT54528                        10. CA022      <- relevante

1 acierto de 10                     2 aciertos de 10
precision@10 = 1/10 = 0,100         precision@10 = 2/10 = 0,200
```

Se llama *precisión* porque mide **qué tan limpio** es lo que devuelve: cuánta
basura viene mezclada. La pregunta que responde es *"de lo que me trajiste,
cuánto me sirve"*.

Se cuenta **por documento y sin repetir**: varios chunks de un mismo documento
relevante son **un** acierto, no cinco. Si no, una configuración que llena el
top-10 con pedazos de un solo documento puntuaría mejor justamente por hacer lo
que hay que evitar.

### `techo`

Acá está la trampa que hace que `precision@k` **no se pueda leer sola**.

La pregunta tiene 6 relevantes y se piden 10 resultados. Aunque el buscador
fuera perfecto, lo mejor que podría hacer es traer esos 6 y llenar los otros 4
con cualquier cosa:

```
techo = 6 / 10 = 0,600
```

**Nunca puede llegar a 1,0.** Así que un `precision@10` de 0,200 no es "20%
bien": es 0,200 sobre un máximo posible de 0,600, o sea **un tercio de lo
alcanzable**.

Por eso las tablas llevan tres columnas juntas:

| columna | qué es |
|---|---|
| `precision@10` | lo que logró |
| `techo` | lo mejor posible con este conjunto de preguntas |
| `% del techo` | **la que importa**: qué fracción de lo alcanzable logró |

El techo promedio del conjunto es **0,433**, porque unas preguntas tienen 6
relevantes y otras 1.

### `encontró` y `en top3`

Para una pregunta con **un solo** documento relevante, `precision@10` tiene techo
0,100 y no dice casi nada. Lo que importa ahí es otra cosa:

- **`encontró`** — en qué porcentaje de las preguntas el documento correcto
  apareció entre los 10.
- **`en top3`** — en qué porcentaje apareció entre los **3 primeros**. Es la que
  más se parece a la experiencia real: un usuario lee los primeros resultados, no
  los diez.

Estas dos columnas aparecieron cuando se agregaron preguntas reales de usuario,
que son de un solo documento. Son las más fáciles de leer de todo el reporte:
`encontró 92% / en top3 86%` se entiende sin explicación.

### `distractores`

Documentos anotados **a propósito** como "parecidos pero incorrectos". Para una
pregunta sobre la cadena de `COL502`, los distractores son otros procesos `COL*`
que verificablemente **no** están en esa cadena.

Sirven para distinguir dos configuraciones que puntúan igual: si una trae 3
distractores y otra 9, la primera es mejor — no solo encuentra, además sabe
**descartar**. Un golden set sin distractores mide si el sistema encuentra, no
si sabe descartar.

---

## Los términos de las configuraciones

### `branches` (ramas, o caminos de búsqueda)

Tres formas de buscar que corren en paralelo:

| rama | cómo busca | para qué sirve |
|---|---|---|
| `vector` | por **significado** (embeddings) | preguntas en lenguaje natural |
| `lexical` | por **palabras** (full-text de Postgres, en español) | términos que aparecen literales |
| `exact` | por **identificador** (`CAC011`, `premium_mo`, `10208`) | cuando la consulta nombra un código |

`vector+exact` significa "corrieron esas dos ramas". `fused` significa las tres.

La rama exacta existe por una razón medida: una consulta `CAC011` por vector
devuelve `MA0037`, `MA0080`, `MA1014`… y **el documento cuyo código es `CAC011`
no aparece**, ni ninguno que contenga el término. Un embedding captura
significado, y un código no significa nada: es una etiqueta.

### `cap` (tope por documento)

**Cuántos chunks como máximo puede aportar un mismo documento.**

Se ve en el ejemplo de arriba: sin tope, `GE010` ocupa dos lugares con dos
pedazos de sí mismo. Con `cap 1` cada documento aporta uno solo, entran más
documentos distintos, y por eso aparece `CA022` — que sin tope quedaba afuera.

El caso extremo: para *"qué procesos hay que ejecutar antes de MGSL006"*, sin
tope el buscador devuelve **10 chunks de MGSL006** y ninguno de los 6 procesos
de su cadena declarada.

**Pero el tope no siempre conviene.** Para una pregunta específica como *"qué
pasa si el importe de ajuste supera la comisión neta"*, la respuesta correcta
**son** varios chunks de `AGL009` y de nadie más. Por eso es un parámetro y no
una regla, y por eso el default no recorta.

### `RRF` (Reciprocal Rank Fusion)

Cómo se combinan las ramas. Cada resultado suma `1 / (60 + posición)` por cada
rama donde aparece, y se ordena por la suma total.

Combina **posiciones**, no puntajes, y eso es a propósito: una distancia coseno
vive en [0, 2] y un `ts_rank_cd` no tiene tope y depende del largo del texto. No
son comparables, y normalizarlos exigiría mínimos y máximos que cambian con cada
consulta.

Un ejemplo de qué logra:

```
vector:  1º CO501   2º COL500   3º CA014
léxico:  1º COL704  2º CO501    3º COL500

CO501   = 1/61 + 1/62 = 0,0325   -> 1º
COL500  = 1/62 + 1/63 = 0,0320   -> 2º
COL704  = 1/61        = 0,0164   -> 3º
CA014   = 1/63        = 0,0159   -> 4º
```

`COL704` salió **primero** en el léxico y termina tercero, debajo de `COL500`,
que salió segundo y tercero. Eso es lo que se quiere de una fusión: **aparecer
en dos ramas vale más que ganar en una sola**, y sale sin calibrar nada.

El `k = 60` es el constante de Cormack et al., el mismo que usa el curso. Un `k`
grande achata la curva y obliga a rankear bien en varias ramas; uno chico deja
que un solo primer puesto domine.

---

## La tabla, leída

Sobre las 36 preguntas del conjunto (30 borradoreadas + 6 reales de usuario):

| config | p@10 | encontró | en top3 | distractores | qué dice |
|---|---:|---:|---:|---:|---|
| `vector` | 0,136 | 78% | 67% | 7 | solo significado |
| `lexical` | 0,033 | 28% | 11% | 3 | solo palabras — muy malo por sí solo |
| `vector+exact` | 0,150 | **92%** | **86%** | **3** | **el más limpio** |
| `fused` | 0,111 | 86% | 75% | 5 | agregar la léxica resta |
| `vector+exact` cap 1 | **0,175** | **92%** | **86%** | 9 | **el que más encuentra** |

En una frase: **la mejor configuración encuentra el documento correcto en el 92%
de las preguntas, y lo pone entre los tres primeros en el 86%.**

De las 6 preguntas reales de usuario, **4 devuelven su documento en el puesto 1**.
Las otras dos lo devuelven en los puestos 41 y 52 — están, pero abajo. Esa es la
diferencia entre lo que la fusión hace bien (meter la respuesta en el conjunto
candidato) y lo que le falta (subirla arriba, que es trabajo de un reranker).

## Lo que estos números NO dicen

**No dicen que la recuperación sea buena.** Mientras `golden_retrieval.json`
esté en `PENDING_REVIEW`, las 30 preguntas las derivó el mismo sistema que se
evalúa contra ellas. Sirven para **comparar configuraciones entre sí**. Para
afirmar calidad hace falta que alguien que conozca el negocio complete las dos
casillas de `review` por pregunta.

**No cubren un tipo de pregunta**, y eso sesga la métrica. Las 30 se derivan de
criterios que dan **varios** documentos relevantes, así que el conjunto premia
traer muchos documentos — y por eso `cap 1` gana. No hay ninguna pregunta
profunda sobre un solo documento. Peor: medirla necesitaría anotar **chunks**
relevantes y no documentos, porque `precision@k` por documento no puede expresar
*"quiero varios chunks de este uno"*.

**No son la calidad de las respuestas**, que es otra capa. Esto mide qué llega
al contexto del generador, no qué contesta el generador con eso.

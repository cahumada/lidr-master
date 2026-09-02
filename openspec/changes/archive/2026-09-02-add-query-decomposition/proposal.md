## Why

Con 35 preguntas escritas por una persona sobre los cuatro módulos del foco hay
material para separar dos fallas que se venían mezclando. De los **85 pares
pregunta-documento**, buscando en un candidato de 60 [VERIFICADO-CORPUS]:

| | pares | |
|---|---:|---|
| ya en el top-10 | 49 (58%) | nada que hacer |
| **rango**: puesto 11 a 60 | 21 (25%) | un reranker los rescata |
| **recall**: afuera del top-60 | 15 (18%) | un reranker **no puede** |

Reordenar no trae lo que no vino. Son conjuntos disjuntos.

### Las 15 fallas de recall son todas de preguntas compuestas

| | top-10 | rango | recall |
|---|---:|---:|---:|
| pregunta simple (1 documento) | 12 | 2 | **0** |
| pregunta compuesta (3+) | 37 | 19 | 15 |

12 de 14 pares simples entran al top-10. Las preguntas de un solo documento ya
están resueltas; el problema es entero de las compuestas.

### Y el documento que falta no es el problema

Diez de los documentos que faltan en una pregunta compuesta son **la respuesta
anotada de una pregunta simple**: `CA003`, `CA908`, `CO001`, `CO501`, `COL001`,
`COL003`, `COL005`, `COL502`, `COL520`, `SI012`.

`CA003` sale en el **puesto 1** de la pregunta sobre los dígitos de la CBU y
está **afuera del top-60** de la compuesta de domiciliación PAC/TRANSBANK, que
lo tiene anotado como relevante. `CA025` y `CO001` salen 1º y 3º solos, y
desaparecen juntos en la compuesta de conversión de propuesta.

El documento es recuperable. **La consulta compuesta es lo que lo entierra.**

## What Changes

Una consulta compuesta se divide en subconsultas, cada una se busca por
separado, y lo que aparece se **agrega** al candidato de la consulta completa.

El orden de la consulta completa **no se toca**. Eso no es prudencia: es el
resultado de haber medido las dos alternativas.

### Lo que se midió antes de elegir

Tres variantes, sobre los mismos 85 pares [VERIFICADO-CORPUS]:

| variante | top-10 | rango | recall | rescata | **rompe** |
|---|---:|---:|---:|---:|---:|
| línea base | 49 | 21 | 15 | — | — |
| fusionar solo las subconsultas | 49 | 23 | 13 | 7 | **7** |
| fusionar completa + subconsultas | 50 | 25 | 10 | 5 | **4** |
| **agregar sin reordenar** | 49 | 28 | **8** | 0 | **0** |

Fusionar solo las partes da **empate exacto**: rescata 7 y rompe 7. La causa es
que RRF sobre subconsultas **diluye** — un documento en el puesto 3 de la
consulta completa y ausente de las tres partes puntúa menos que uno en el puesto
20 de la completa y en el 5 de dos partes.

Agregar sin reordenar no puede romper nada por construcción, y es la única de
las tres que no rompe.

### El resultado

| | base | con descomposición |
|---|---:|---:|
| recall del candidato | 70/85 (82%) | **77/85 (91%)** |
| alcanzable por un reranker | 21 | **28** |
| pares en top-10 | 49 | 49 |
| regresiones | — | **0** |

**Los pares en top-10 no se mueven, y eso es lo esperado**: la descomposición no
ordena, hace que el documento entre. Ordenar es del reranker. Este cambio no se
mide en `precision@10` sino en el recall del candidato, y su valor es que el
conjunto que el reranker puede atacar crece de 21 a 28 pares.

Siete documentos que ningún reranking podía alcanzar ahora están en el candidato:
`CA003` y `CO632` en la de domiciliación, `CA001k` y `CA001M` en la de traspaso,
`CO001` y `CA025` en la de conversión.

### Dos formas de coordinación, no una

La primera son **cláusulas coordinadas**, cada una con su interrogativo:

    [contexto], ¿cómo aaa, cómo bbb y en qué ccc?

El contexto lleva las entidades (`PAC`, `TRANSBANK`, el recibo), así que se
reparte a cada subconsulta. Sin eso, *"cómo se originan esos boletines"* no dice
nada.

La segunda son **frases nominales coordinadas** que comparten el interrogativo y
el verbo:

    ¿Cómo puedo consultar [A], [B] y [C]?

Esta segunda forma es la que dejaba afuera las compuestas de tres documentos del
diseñador y de siniestros. Con solo la primera el recall llegaba a 88%; con las
dos, a 91%.

### Lo que NO hace

- **No usa un LLM.** El curso tiene `query_transform.py` con un modelo. Acá las
  reglas alcanzan para 20 de las 24 preguntas compuestas, son deterministas y se
  testean sin red. Las 4 que quedan son enumeraciones de sustantivos sin
  determinante (*"secuencia de ventanas, variables de clave inicial y
  validaciones de clientes"*), que es donde una regla se vuelve frágil y un
  modelo gana. Queda anotado con su número, no descartado.
- **No divide preguntas simples.** De las 15 que el divisor deja intactas, 11 son
  de un solo documento. Ese es el comportamiento correcto: la variante que las
  partía rompió `U-SI501-reasignar`, que ya estaba resuelta.
- **No reordena.** Ver la tabla de arriba.

## Impact

- `app/generation/rag/retrieval/decomposition.py` nuevo: el divisor.
- `HybridRetriever.retrieve()` acepta `decompose=` y agrega candidatos.
- Costo: una consulta compuesta hace 2 o 3 búsquedas en vez de 1. El largo del
  candidato pasa de 60 a 60-135, con media 60.
- Sin dependencias nuevas.

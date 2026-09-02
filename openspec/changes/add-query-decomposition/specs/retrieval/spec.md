# retrieval Delta Specification

## ADDED Requirements

### Requirement: Una pregunta compuesta DEBE preguntarse también por partes
Los usuarios de este sistema no preguntan una cosa por vez. De las 35 preguntas
reales del golden set, 24 son compuestas, y ahí está **toda** la pérdida de
recall: los 15 pares pregunta-documento cuyo documento no aparecía en un
candidato de 60 son de preguntas compuestas, y ninguno de preguntas simples.

El documento no es el problema. Diez de los que faltaban son la respuesta
anotada de otra pregunta, simple, del mismo conjunto: `CA003` sale **primero**
para *"cuántos dígitos tiene la CBU"* y está afuera del top-60 de la pregunta de
domiciliación PAC/TRANSBANK que lo tiene anotado como relevante.

Es la consulta compuesta la que lo entierra, así que se pregunta también por
partes y lo que las partes encuentran se agrega al candidato.

#### Scenario: Cláusulas coordinadas
- **WHEN** la pregunta tiene varias cláusulas, cada una con su interrogativo
- **THEN** se divide en una subconsulta por cláusula
- **AND** el contexto anterior al `¿` aparece en todas, porque ahí están las
  entidades

#### Scenario: Frases nominales coordinadas
- **WHEN** la pregunta comparte un interrogativo y un verbo entre varias frases
  nominales, cada una encabezada por un determinante
- **THEN** se divide en una subconsulta por frase, con la cabeza compartida

#### Scenario: Una pregunta simple no se divide
- **WHEN** la pregunta hace una sola cosa
- **THEN** el divisor devuelve una lista vacía y se busca una sola vez

#### Scenario: Una coma que no separa preguntas no divide
- **WHEN** la coma precede a una subordinada y no a un interrogativo ni a un
  determinante
- **THEN** la pregunta no se divide

### Requirement: La descomposición NO DEBE cambiar el orden de lo que ya se encontraba
Se midieron tres formas de combinar las subconsultas con la consulta completa
[VERIFICADO-CORPUS]:

| variante | rescata al top-10 | **rompe** |
|---|---:|---:|
| fusionar solo las subconsultas | 7 | **7** |
| fusionar completa + subconsultas | 5 | **4** |
| agregar sin reordenar | 0 | **0** |

Fusionar solo las partes da empate exacto porque RRF **diluye**: un documento en
el puesto 3 de la consulta completa y ausente de las tres partes puntúa menos
que uno en el puesto 20 de la completa y en el 5 de dos partes.

Por eso el candidato empieza con exactamente lo que devolvió la consulta
completa, en su orden, y las subconsultas solo aportan lo que no estaba.

#### Scenario: El prefijo se conserva
- **WHEN** se descompone una consulta
- **THEN** el resultado empieza con los mismos chunks y en el mismo orden que
  sin descomponer

#### Scenario: Lo agregado llena lugares vacíos
- **WHEN** la consulta completa devuelve menos resultados que el límite pedido
- **THEN** las subconsultas llenan los puestos libres sin desplazar nada

### Requirement: La descomposición DEBE medirse por recall del candidato y no por precision@k
`precision@10` no se mueve con este cambio —0,140 antes y después— y reportarlo
solo con esa métrica lo haría parecer inútil.

No lo es, y la razón es una división de trabajo: la descomposición hace que el
documento **entre** al candidato; ordenarlo es de un reranker. Medida en lo que
le corresponde, sobre las 35 preguntas humanas [VERIFICADO-CORPUS]:

| | base | con descomposición |
|---|---:|---:|
| `recall@60` | 70/85 (82%) | **77/85 (91%)** |
| pares alcanzables por un reranker | 21 | **28** |
| pares perdidos | 15 | **8** |
| regresiones | — | **0** |

#### Scenario: El reporte separa rango de recall
- **WHEN** se evalúa una configuración
- **THEN** se reporta cuántos pares están en el top-k, cuántos entre el puesto
  k+1 y el ancho del candidato, y cuántos afuera
- **AND** los del medio son los que un reranker puede convertir; los de afuera
  no, porque reordenar no trae lo que no vino

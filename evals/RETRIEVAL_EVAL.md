# Evaluación de recuperación — precision@k sobre el golden set

> Si la terminología de acá abajo no te dice nada, empezá por
> [COMO_LEER.md](COMO_LEER.md): explica cada término sobre una pregunta real.

## Cómo leer estos números

`precision@10 = aciertos / 10`, contado por documento y sin duplicados: varios
chunks de un documento relevante son un acierto, no cinco. Si no, una
configuración que inunda el top-k con un solo documento puntuaría mejor por hacer
justamente lo que hay que evitar.

El **techo** es el mejor `precision@10` que el conjunto permite: una pregunta con
3 relevantes y k=10 no puede pasar de 0.30. Un puntaje de 0,28 sobre un techo
de 0,30 y uno de 0,28 sobre un techo de 1,00 son resultados muy distintos, y el
número solo no los distingue.

**Distractores** cuenta cuántos documentos deliberadamente parecidos-pero-irrelevantes
entraron al top-k. Dos configuraciones con el mismo puntaje no son iguales si una
se come más distractores.

## Resultados

| Config | precision@10 | techo | % del techo | distractores | ms/consulta |
|---|---:|---:|---:|---:|---:|
| `vector` | 0.130 | 0.345 | 38% | 7 | 494.8 |
| `lexical` | 0.057 | 0.345 | 17% | 2 | 957.3 |
| `vector+exact` | 0.141 | 0.345 | 41% | 3 | 464.6 |
| `fused` | 0.121 | 0.345 | 35% | 4 | 1733.7 |
| `vector+exact cap1` | 0.177 | 0.345 | 51% | 9 | 453.9 |
| `vector+exact cap2` | 0.163 | 0.345 | 47% | 7 | 531.5 |
| `vector+exact cap3` | 0.154 | 0.345 | 45% | 6 | 498.3 |
| `fused cap1` | 0.148 | 0.345 | 43% | 7 | 1638.1 |
| `vector cap1` | 0.168 | 0.345 | 49% | 9 | 416.2 |

## Por tipo de pregunta

| Tipo | preguntas | `vector` | `lexical` | `vector+exact` | `fused` | `vector+exact cap1` | `vector+exact cap2` | `vector+exact cap3` | `fused cap1` | `vector cap1` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `by_code` | 12 | 0.058 | 0.025 | 0.100 | 0.100 | 0.100 | 0.100 | 0.100 | 0.100 | 0.067 |
| `declared_precedence` | 2 | 0.100 | 0.200 | 0.100 | 0.100 | 0.300 | 0.250 | 0.250 | 0.300 | 0.300 |
| `field_validations` | 16 | 0.225 | 0.013 | 0.225 | 0.131 | 0.269 | 0.250 | 0.237 | 0.169 | 0.269 |
| `user_question` | 26 | 0.108 | 0.088 | 0.112 | 0.127 | 0.146 | 0.131 | 0.119 | 0.146 | 0.142 |

### Qué significa cada tipo

- **`declared_precedence`**: El corpus declara la dependencia. Es el tipo mejor fundado.
- **`field_validations`**: Relevancia por metadata.field exacto. Ojo: favorece a la busqueda lexica, porque el nombre del campo aparece literalmente en el texto.
- **`by_code`**: Un solo relevante. Es el caso que la busqueda vectorial no puede responder y por el que existe la rama exacta.

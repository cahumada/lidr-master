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
| `vector` | 0.134 | 0.376 | 36% | 7 | 504.1 |
| `vector+exact` | 0.146 | 0.376 | 39% | 3 | 523.0 |
| `fused` | 0.115 | 0.376 | 31% | 5 | 1239.6 |
| `vector+exact cap1` | 0.176 | 0.376 | 47% | 9 | 524.4 |
| `vector+exact cap2` | 0.166 | 0.376 | 44% | 7 | 595.8 |

## Por tipo de pregunta

| Tipo | preguntas | `vector` | `vector+exact` | `fused` | `vector+exact cap1` | `vector+exact cap2` |
|---|---:|---:|---:|---:|---:|---:|
| `by_code` | 12 | 0.058 | 0.100 | 0.100 | 0.100 | 0.100 |
| `declared_precedence` | 2 | 0.100 | 0.100 | 0.100 | 0.200 | 0.200 |
| `field_validations` | 16 | 0.225 | 0.225 | 0.138 | 0.269 | 0.250 |
| `user_question` | 11 | 0.091 | 0.091 | 0.100 | 0.118 | 0.109 |

### Qué significa cada tipo

- **`declared_precedence`**: El corpus declara la dependencia. Es el tipo mejor fundado.
- **`field_validations`**: Relevancia por metadata.field exacto. Ojo: favorece a la busqueda lexica, porque el nombre del campo aparece literalmente en el texto.
- **`by_code`**: Un solo relevante. Es el caso que la busqueda vectorial no puede responder y por el que existe la rama exacta.

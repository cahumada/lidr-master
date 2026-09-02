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
| `vector` | 0.136 | 0.378 | 36% | 7 | 633.9 |
| `lexical` | 0.033 | 0.378 | 9% | 3 | 272.4 |
| `vector+exact` | 0.150 | 0.378 | 40% | 3 | 513.7 |
| `fused` | 0.111 | 0.378 | 29% | 5 | 809.7 |
| `vector+exact cap1` | 0.175 | 0.378 | 46% | 9 | 520.7 |

## Por tipo de pregunta

| Tipo | preguntas | `vector` | `lexical` | `vector+exact` | `fused` | `vector+exact cap1` |
|---|---:|---:|---:|---:|---:|---:|
| `by_code` | 12 | 0.058 | 0.025 | 0.100 | 0.100 | 0.100 |
| `declared_precedence` | 2 | 0.100 | 0.200 | 0.100 | 0.100 | 0.200 |
| `field_validations` | 16 | 0.225 | 0.013 | 0.225 | 0.138 | 0.269 |
| `user_question` | 6 | 0.067 | 0.050 | 0.067 | 0.067 | 0.067 |

### Qué significa cada tipo

- **`declared_precedence`**: El corpus declara la dependencia. Es el tipo mejor fundado.
- **`field_validations`**: Relevancia por metadata.field exacto. Ojo: favorece a la busqueda lexica, porque el nombre del campo aparece literalmente en el texto.
- **`by_code`**: Un solo relevante. Es el caso que la busqueda vectorial no puede responder y por el que existe la rama exacta.

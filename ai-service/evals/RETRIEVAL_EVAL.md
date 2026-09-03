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
| `vector+exact cap1` | 0.140 | 0.243 | 58% | 0 | 508.6 |
| `vector+exact cap1 +split` | 0.140 | 0.243 | 58% | 0 | 1105.5 |
| `+split +rerank lexico` | 0.151 | 0.243 | 62% | 0 | 1171.2 |
| `+split +rerank modelo` | 0.171 | 0.243 | 71% | 0 | 3136.0 |

## Por tipo de pregunta

| Tipo | preguntas | `vector+exact cap1` | `vector+exact cap1 +split` | `+split +rerank lexico` | `+split +rerank modelo` |
|---|---:|---:|---:|---:|---:|
| `user_question` | 35 | 0.140 | 0.140 | 0.151 | 0.171 |

### Qué significa cada tipo

- **`declared_precedence`**: El corpus declara la dependencia. Es el tipo mejor fundado.
- **`field_validations`**: Relevancia por metadata.field exacto. Ojo: favorece a la busqueda lexica, porque el nombre del campo aparece literalmente en el texto.
- **`by_code`**: Un solo relevante. Es el caso que la busqueda vectorial no puede responder y por el que existe la rama exacta.

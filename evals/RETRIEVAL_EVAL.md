# Evaluación de recuperación — precision@k sobre el golden set

> **El golden set está PENDIENTE DE REVISIÓN.**
> 22 de 22 preguntas no fueron revisadas por nadie que
> conozca el negocio. Un golden set borradoreado por el mismo sistema que se
> evalúa contra él no mide la calidad del sistema: mide si el sistema coincide
> consigo mismo. Los números de acá abajo sirven para **comparar
> configuraciones entre sí**, no para afirmar que la recuperación es buena.

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
| `vector+exact` | 0.150 | 0.427 | 35% | 3 | 787.8 |
| `vector+exact cap1` | 0.227 | 0.427 | 53% | 7 | 642.1 |
| `vector+exact cap2` | 0.195 | 0.427 | 46% | 6 | 594.9 |
| `vector+exact cap3` | 0.182 | 0.427 | 43% | 4 | 572.1 |

## Por tipo de pregunta

| Tipo | preguntas | `vector+exact` | `vector+exact cap1` | `vector+exact cap2` | `vector+exact cap3` |
|---|---:|---:|---:|---:|---:|
| `by_code` | 6 | 0.100 | 0.100 | 0.100 | 0.100 |
| `declared_precedence` | 10 | 0.100 | 0.190 | 0.180 | 0.170 |
| `field_validations` | 6 | 0.283 | 0.417 | 0.317 | 0.283 |

### Qué significa cada tipo

- **`declared_precedence`**: El corpus declara la dependencia. Es el tipo mejor fundado.
- **`field_validations`**: Relevancia por metadata.field exacto. Ojo: favorece a la búsqueda léxica, porque el nombre del campo aparece literalmente en el texto.
- **`by_code`**: Un solo relevante. Es el caso que la búsqueda vectorial no puede responder y por el que existe la rama exacta.

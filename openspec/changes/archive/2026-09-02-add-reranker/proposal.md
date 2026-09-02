## Why

La descomposición dejó el trabajo a medio hacer, y a propósito: metió los
documentos al candidato sin cambiar `precision@10`. Después de ella, de los 85
pares pregunta-documento del golden set, **27 tienen su documento en el
candidato de 60 pero afuera del top-10**.

Eso es un problema de rango, y es lo único que un reranker puede arreglar.

### Cuánto hay para ganar

Medido con un oráculo —un reranker perfecto que pone adelante los relevantes que
ya están en el candidato— sobre las 35 preguntas humanas [VERIFICADO-CORPUS]:

| | pares en top-10 | `p@10` |
|---|---:|---:|
| sin reordenar | 49 | 0,140 |
| **oráculo** | **77** | **0,220** |

28 pares para convertir, y el techo del oráculo es el 91% del techo teórico de
`precision@10` para este conjunto (0,243).

### Lo que se midió antes de elegir

| reranker | pares en top-10 | `p@10` | de los 28 |
|---|---:|---:|---:|
| ninguno | 49 | 0,140 | — |
| léxico determinista | 53 | 0,151 | +4 |
| **con modelo** | **57-59** | **0,163-0,169** | **+8 a +10** |
| oráculo | 77 | 0,220 | +28 |

El léxico saca 4 de 28. Es poco, y por eso el modelo se gana la latencia.

## What Changes

`Reranker` como `Protocol`, con dos implementaciones —igual que `Embedder` tiene
`OpenAIEmbedder` y `HashEmbedder`:

- **`LLMReranker`**: una llamada por consulta con los 60 candidatos, devuelve los
  ids ordenados. Es el default cuando hay clave.
- **`LexicalReranker`**: coincidencia de título y texto sobre el rango fusionado.
  Sin red y sin clave, así que es lo que usan los tests y cualquier corrida sin
  conexión. Vale +4 medidos, que le gana a un 0 sin medir.

`retrieve()` acepta `reranker=`, ensancha el candidato a 60, reordena y recorta a
`limit`. Ensanchar es todo el punto: reordenar los mismos 10 que la búsqueda ya
eligió no tiene con qué trabajar.

### Un reranker NO puede ser libre de regresiones

Es la diferencia importante con la descomposición, que sí lo es por
construcción. Reordenar dentro de 10 puestos es **de suma cero**: promover un
documento al top-10 baja a otro. Medido, el de modelo rescata 15-16 pares y
**rompe 6-7**. Lo que lo justifica es el neto, no la ausencia de daño, y eso hay
que decirlo antes de reportar el número.

### Lo que movió la aguja no fue el modelo

`gpt-4o` sacó **exactamente el mismo** +11 que `gpt-4o-mini` en la corrida donde
se compararon, a 5,6 s contra 3,3 s. El modelo no era el cuello de botella, así
que el default es el barato.

Lo que sí movió la aguja fue **decirle qué significa un sufijo `_k`**. Los tres
documentos que el reranker empujaba afuera del top-10 eran `DP003_k`, `CA001k` y
`CA001k`: todas transacciones de encabezado. El modelo no las elegía porque
*"Solicitud de clave para..."* parece un formulario, cuando en esta arquitectura
es el punto de acceso y lleva la descripción funcional completa —`CA001k` tiene
338 chunks, `CA001A` ("Tratamiento de pólizas") tiene 4.

Agregar esa frase al prompt **bajó las roturas de 10-11 pares a 5-7**. Es
conocimiento de dominio ya documentado en
`openspec/domain/visualtime-window-types.md`, y no una filtración de las
anotaciones: dice qué significa un sufijo, nunca qué documento responde qué.

### `temperature=0` no es determinismo

Tres corridas idénticas dieron 57, 58 y 59 pares. Por eso la ganancia se reporta
como **rango, +8 a +10**, y no como el mejor número que salió.

## Impact

El pipeline completo, sobre las 35 preguntas humanas [VERIFICADO-CORPUS]:

| | `p@10` | encontró | `recall@60` | rango | perdidos | latencia |
|---|---:|---:|---:|---:|---:|---:|
| `vector+exact cap1` | 0,140 | 86% | 82% | 21 | 15 | 509 ms |
| `+split` | 0,140 | 86% | 89% | 27 | 9 | 1.106 ms |
| `+split +rerank léxico` | 0,151 | 89% | 91% | 24 | 8 | 1.171 ms |
| **`+split +rerank modelo`** | **0,171** | **94%** | 91% | **17** | 8 | 3.136 ms |

`p@10` sube 22% y el hallazgo pasa de 86% a 94%. Los pares en problema de rango
bajan de 27 a 17: diez convertidos.

- `app/generation/rag/retrieval/reranker.py` nuevo.
- `Settings.RERANK_MODEL`, default `gpt-4o-mini`.
- `get_reranker()` en `dependencies.py`, que cae al léxico sin clave en lugar de
  fallar.
- Sin dependencias nuevas: `openai` ya estaba para los embeddings.
- Costo: una llamada de ~5k tokens de entrada por consulta, y la latencia se
  triplica.

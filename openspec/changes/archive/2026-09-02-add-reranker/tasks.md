# Tareas

## 1. Medir antes de construir

- [x] 1.1 El oráculo: cuántos pares es capaz de convertir un reranker perfecto.
      28 de 85, `p@10` 0,140 → 0,220, que es el 91% del techo teórico.
- [x] 1.2 Qué señales que ya viajan en la fila discriminan. Coincidencia de
      título 66% en relevantes contra 32% en no relevantes; `bullet_path`
      (53%/52%) y `section` (100%/100%) no sirven.
- [x] 1.3 Reranker determinista: +4 de 28. Poco, y es lo que justifica el modelo.

## 2. El reranker

- [x] 2.1 `Reranker` como `Protocol`, igual que `Embedder`.
- [x] 2.2 `LexicalReranker`: título + texto + sección sobre el rango fusionado
      como prior. Sin red ni clave.
- [x] 2.3 `LLMReranker`: una llamada con los 60 candidatos, devuelve ids
      ordenados.
- [x] 2.4 Los ids inventados se descartan Y se cuentan. 1 en 35 consultas con
      `gpt-4o-mini`.
- [x] 2.5 Un fallo del modelo devuelve los candidatos intactos, no propaga.
- [x] 2.6 `rerank()` devuelve TODOS los candidatos: el recorte es del llamador.

## 3. Integración

- [x] 3.1 `retrieve()` acepta `reranker=` y ensancha el candidato a
      `rerank_candidates` antes de reordenar.
- [x] 3.2 El reordenamiento va sobre los chunks HIDRATADOS: sin título ni texto
      no hay nada que juzgar.
- [x] 3.3 `Settings.RERANK_MODEL`, default `gpt-4o-mini`.
- [x] 3.4 `get_reranker()` cae al léxico sin clave en lugar de fallar, al
      contrario de `get_embedder()`. La diferencia está justificada en el
      docstring.

## 4. Tests, sin red

- [x] 4.1 Palabras de contenido: cortas fuera, acentos normalizados, stopwords
      fuera.
- [x] 4.2 El léxico promueve una coincidencia de título y respeta el orden
      original cuando no hay señal.
- [x] 4.3 El de modelo con un cliente falso: ranking aplicado, id inventado
      descartado, id repetido no duplicado.
- [x] 4.4 Un modelo que falla y un JSON roto no levantan.
- [x] 4.5 Sin candidatos no se llama al modelo.
- [x] 4.6 El prompt lleva todos los ids y la pregunta.
- [x] 4.7 Las dos implementaciones cumplen el `Protocol`. 19 tests.

## 5. Medición

- [x] 5.1 Comparar `gpt-4o` contra `gpt-4o-mini`. Mismo +11, 5,6 s contra 3,3 s:
      el modelo no es el cuello de botella.
- [x] 5.2 Diagnosticar por qué se queda lejos del oráculo. Devuelve menos de 10
      ids en 25 de 35 consultas, y empuja afuera del top-10 a `DP003_k`,
      `CA001k` y `CA001k` — las tres transacciones de encabezado.
- [x] 5.3 Probar si fusionar por RRF protege el orden base. NO: con hasta 10
      elegidos todo lo elegido le gana a todo lo no elegido, y el resultado es
      idéntico a concatenar.
- [x] 5.4 Agregar al prompt qué significa un sufijo `_k`. Roturas de 10-11 a 5-7.
- [x] 5.5 Medir la varianza entre corridas idénticas. 57-59 pares con
      `temperature=0`, así que la ganancia se reporta como rango.
- [x] 5.6 `CONFIGS` con `+split +rerank lexico` y `+split +rerank modelo`.
      `Config` pasa a `NamedTuple` porque cuatro valores posicionales, dos
      booleanos, dejaron de leerse.
- [x] 5.7 El pipeline completo sobre las 35 humanas [VERIFICADO-CORPUS]:

      | | `p@10` | encontró | `recall@60` | rango | perdidos | latencia |
      |---|---:|---:|---:|---:|---:|---:|
      | `vector+exact cap1` | 0,140 | 86% | 82% | 21 | 15 | 509 ms |
      | `+split` | 0,140 | 86% | 89% | 27 | 9 | 1.106 ms |
      | `+split +rerank léxico` | 0,151 | 89% | 91% | 24 | 8 | 1.171 ms |
      | `+split +rerank modelo` | **0,171** | **94%** | 91% | **17** | 8 | 3.136 ms |

## 6. Cierre

- [x] 6.1 `pytest`, `pytest -m integration`, `ruff check .` y `validate_specs`
      en verde.
- [x] 6.2 Promover el delta y archivar, junto con `add-query-decomposition`.

# Tareas

## 1. El divisor

- [x] 1.1 `decomposition.py` con `decompose(question) -> list[str]`, que
      devuelve lista vacía cuando la pregunta no es compuesta.
- [x] 1.2 Forma de cláusulas coordinadas: límite en coma o `y`/`e` seguida de
      interrogativo, con el contexto repartido a cada parte.
- [x] 1.3 Forma de frases nominales coordinadas: cabeza compartida hasta el
      primer determinante, límite en coma o `y` seguida de determinante.
- [x] 1.4 Cláusulas primero, nominales después. La de cláusulas es más
      específica.

## 2. Tests del divisor, sin base ni red

- [x] 2.1 Una pregunta simple NO se divide.
- [x] 2.2 Una compuesta de tres cláusulas da tres subconsultas.
- [x] 2.3 El contexto aparece en TODAS las subconsultas — es donde están las
      entidades.
- [x] 2.4 Una coma que no precede a un interrogativo no divide.
- [x] 2.5 Frases nominales coordinadas: la cabeza compartida aparece en todas.
- [x] 2.6 Una enumeración sin determinantes no se divide (el caso que queda para
      un modelo, fijado como límite conocido).
- [x] 2.7 Las preguntas reales del golden set que dieron cada forma, como casos
      de regresión. 11 tests, todos con preguntas del conjunto de 35.

## 3. Integración con la recuperación

- [x] 3.1 `HybridRetriever.retrieve()` acepta `decompose_query=` y por default
      NO descompone: el cambio es aditivo y medible por separado.
- [x] 3.2 El candidato es la consulta completa y después lo que las
      subconsultas agregan, fusionadas entre sí por RRF. El prefijo NO se toca.
- [x] 3.3 Test: agregar al final de la lista no puede cambiar el prefijo que
      sale de `cap_per_group`, que es un filtro en streaming. Es la garantía de
      cero regresiones y está fijada por test, no por comentario.
- [x] 3.4 Test: lo agregado llena los puestos que la consulta completa dejó
      vacíos, sin desplazar nada.

## 4. Medición

- [x] 4.1 `eval_retrieval.py` reporta `recall@60`, pares de rango y pares
      perdidos, no solo `precision@k`. Sin eso este cambio se lee como que no
      hizo nada.
- [x] 4.2 `vector+exact cap1 +split` en `CONFIGS`, y `--human-only` para no
      mezclar las 30 borradoreadas sin revisar.
- [x] 4.3 Verificado sobre las 35 humanas, con el código de producción y no con
      el proxy [VERIFICADO-CORPUS]:

      | | base | +split |
      |---|---:|---:|
      | `recall@60` | 82% | **91%** |
      | pares de rango (alcanzables por un reranker) | 21 | **28** |
      | pares perdidos | 15 | **8** |
      | `p@10` | 0,140 | 0,140 |
      | latencia | 499 ms | 1.209 ms |

      `p@10` no se mueve, y es lo esperado. La latencia se multiplica por 2,4:
      una compuesta hace 3 o 4 búsquedas en lugar de 1.

- [x] 4.4 De los 8 pares perdidos que quedan, **solo 1 está en una pregunta que
      el divisor no parte** (`SIC002` en `U-multi-consulta-siniestros`). Los
      otros 7 están en preguntas que SÍ se partieron, así que descomponer mejor
      no los trae.

      **Eso descarta el LLM con un número.** El techo de un divisor con modelo
      sobre este conjunto es 1 par de 85. Los otros 7 —`COL502` dos veces,
      `COL001`, `COL520`, `CA908`, `DP018G`, `CO632_k`— necesitan otra cosa:
      expansión por el grafo de `process_map_edges` es el candidato, porque ya
      se midió que en cobranzas lleva 9/18 a 14/18.

- [x] 4.5 Medir la descomposicion contra agregar la rama lexica, que ataca lo
      mismo. Gana la descomposicion: 91% contra 86% de `recall@60`, 8 perdidos
      contra 12, y 2,3 veces mas rapida. Y sobre `fused` no aporta nada, que es
      la interaccion documentada en `design.md` §6.

## 5. Cierre

- [x] 5.1 `pytest` (411), `pytest -m integration` (25), `ruff check .` y
      `validate_specs` en verde.
- [x] 5.2 Promover el delta y archivar.

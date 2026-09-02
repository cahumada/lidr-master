## Why

El proyecto arrancó con esta premisa: trocear los documentos funcionales de todos
los módulos y después **relacionarlos entre sí para armar un mapa de procesos que
viva en el CAG**. El troceado, los embeddings y el store están; el mapa no, y es
parte del entregable.

Un CAG solo tiene sentido si lo que se precarga **entra** en la ventana de
contexto. Medido [VERIFICADO-CORPUS]:

| | | |
|---|---:|---:|
| Árbol de ventanas (`WINDOWS`) | 3.389 nodos | 53.780 tokens |
| Catálogo de documentos | 2.219 | 30.441 tokens |
| Secciones `Requisitos` | 252 chunks | 10.879 tokens |
| **Total** | | **95.100 tokens** |

**48% de una ventana de 200k.** Entra con margen, que es la condición de
viabilidad. Si no entrara, sería un RAG con pasos de más.

Y el orden importa: el mapa es un **insumo** de la recuperación (expandir por
referencias) y de la generación (citar y navegar). Construirlo antes hace que
esas capas lo puedan usar; al revés no gana nada.

## Qué relaciones existen de verdad, y cuáles no

Esto se midió antes de diseñar, porque el alcance del mapa depende de lo que la
documentación realmente dice.

**Jerarquía de navegación — sólida pero con huecos.** El árbol `WINDOWS` tiene
3.389 nodos con `parent_code`, y **794 (23%) no son alcanzables desde ningún
menú**: transacciones reales —`CPL011` "Asientos automáticos de primas",
`VI7001`, `MA5565`— que existen como ventana y no cuelgan de ninguna opción.

El número se corrigió durante la implementación. "Sin padre" son 717, pero 3 de
esos **tienen hijos**, y cada descendiente de un subárbol colgado de la nada es
tan inalcanzable como su raíz; sumando eso son 794. Contar solo los sin padre
subcontaba por 80. La medida correcta es si el camino llega a la raíz, que
`NavigationTree.path()` ya resuelve y a prueba de ciclos.

Que 794 transacciones no cuelguen de un menú **es información del mapa**, no un
defecto de la extracción: se ejecutan desde código o desde otra transacción, y
saberlo es parte de entender el sistema.

**Dependencias de ejecución — reales, explícitas y POCAS.** 228 documentos
tienen sección `Requisitos`, pero eso engaña. Clasificadas
[VERIFICADO-CORPUS]:

| | |
|---|---:|
| `No aplica.` | 122 |
| Otro tipo de requisito (permisos, datos, "proceso nocturno") | 105 |
| **Declaran precedencia de ejecución** | **25** |

De esos 25 salen **39 aristas** con destino existente en el corpus, más 6 que
declaran precedencia sin nombrar un código (*"previamente se debe ejecutar la
interfaz que alimenta la tabla temporal"* — dependencia real, destino no
nombrable).

El conteo subió de 9 a 15 a 39 según cómo se extrae, y eso es parte del diseño:

- **9** buscando en cada chunk por separado. La sección `Requisitos` de `COL502`
  produce 4 chunks —3 de tabla con los códigos y 1 narrativo con el enunciado—
  así que por chunk el enunciado y sus códigos nunca se ven.
- **15** leyendo la **sección** completa y tomando los enlaces markdown.
- **39** tomando además los códigos que están como **texto plano**: `COL520`
  escribe `Código: COL500 Descripción: Generación de cobranzas` sin enlazarlos.

Las cadenas reales son cortas y creíbles: `MGSL006` depende de 6 procesos,
`CRL007` y `CRL050` de 4 cada uno, `COL502` y `COL520` de 3.

**Esto no es "el mapa de procesos del sistema".** Son las precedencias que la
documentación declara, que es otra cosa y bastante menor. El volumen del mapa lo
aportan la jerarquía y las referencias; la precedencia aporta las 39 aristas que
se pueden afirmar.

**Referencias cruzadas — 1.456 aristas internas** por enlaces HTML, más 1.278
que el chunker ya extrae como `references`. Pero el 39% de los documentos no es
alcanzado por ninguna, y los mayores enlazadores son documentos índice
(`LIFE_INDEX` con 130), o sea que buena parte de esas aristas son tabla de
contenidos y no relación de negocio.

**Lo que NO está en el corpus:** un flujo completo de todas las transacciones.
Fuera de esos 228 documentos, la documentación no dice "después de X viene Y".
Un mapa que lo afirmara estaría inventando.

## What Changes

- **`app/generation/rag/process_map/`** — construir el grafo desde tres fuentes:
  el árbol de ventanas, las secciones `Requisitos` y las referencias cruzadas.
  Cada arista lleva **de qué fuente salió**, porque no tienen la misma fuerza:
  una dependencia declarada es una afirmación del documento, un enlace de un
  índice es una tabla de contenidos.
- **Tres tipos de arista**: `menu_parent` (jerarquía), `requires` (precedencia
  declarada) y `references` (mención cruzada). Nunca mezclados en una sola.
- **`scripts/build_process_map.py`** — escribe `data/process_map.json` y el
  contexto precargable del CAG, con su cuenta de tokens medida y no estimada.
- **Un reporte de cobertura que dice lo que falta**: cuántas transacciones no
  cuelgan de un menú, cuántos nodos no tienen documento, cuántos documentos no
  son ventana. Un mapa que no declara sus huecos se lee como completo.
- **Tabla `process_map_edges`** en Postgres, para que la recuperación pueda
  expandir por referencias sin cargar el JSON.

## Capabilities

### Capability nueva

- `process-map`: el grafo de transacciones del sistema y el contexto precargable
  que se deriva de él.

## Impact

- `app/generation/rag/process_map/{__init__,graph.py,requisites.py,cag.py}` — nuevos.
- `app/generation/rag/store/models.py` + una migración — `process_map_edges`.
- `scripts/build_process_map.py` — nuevo.
- `app/config.py` — techo de tokens del contexto del CAG.

## Lo que este cambio NO hace

- **No infiere aristas.** Si la documentación no declara una precedencia, el mapa
  no la tiene. Deducirla de que dos procesos comparten una tabla sería inventar
  una relación de negocio a partir de una coincidencia técnica.
- **No genera respuestas.** Produce el contexto precargable; usarlo es de la
  capability de generación.
- **No expone un endpoint.** El mapa es un artefacto y una tabla; quién lo sirve
  se decide cuando haya un consumidor.

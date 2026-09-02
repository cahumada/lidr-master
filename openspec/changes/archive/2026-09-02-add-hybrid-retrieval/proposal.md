## Why

El store responde búsquedas por similitud, y con eso se puede medir por primera
vez qué tan bien recupera. La medición dice que la similitud sola **no alcanza**,
y no por poco.

### El vector no encuentra un documento por su propio código

Consulta `CAC011` sobre las 57.101 filas [VERIFICADO-CORPUS]:

| | primeros 5 documentos |
|---|---|
| vector | `MA0037`, `MA0080`, `MA1014`, `SCA500`, `SCA500` |
| full-text | **`CAC011`**, `POLICIES_INDEX`, `CA001k`, `CA001k`, `CA001k` |

El documento cuyo código **es** `CAC011` no aparece entre los cinco primeros del
vector, y ninguno de esos cinco contiene el término literal. El full-text lo trae
primero. Lo mismo con `premium_mo` (nombre de tabla) y `nReceipt` (nombre de
campo): cero solapamiento entre los dos rankings.

Esto no es un ajuste fino. Un usuario que pregunta por `CAC011` —que es cómo se
habla de estas transacciones— hoy no lo encuentra.

### El full-text tampoco alcanza solo, y por una razón concreta

`plainto_tsquery` combina **todos** los términos con `AND`:

- `codigo de error 10208` → `'codig' & 'error' & '10208'` → **0 resultados**,
  aunque `10208` está en 2 chunks: no están junto a las palabras "código" y
  "error".
- `tabla premium_mo` → `'tabl' & 'premium' & 'mo'` → el guion bajo parte el
  identificador en dos.

### Y los resultados se apilan en un solo documento

Sobre 8 preguntas reales, el documento dominante se lleva **4,5 de 10** hits en
promedio, y en 2 de las 8 se lleva 5 o más. El peor caso se lleva 10 de 10.

Pero esto **no siempre es un defecto**: *"qué pasa si el importe de ajuste supera
la comisión neta"* es una pregunta sobre la lógica de `AGL009`, y que sus 10
chunks vengan de `AGL009` es correcto. La concentración es un problema para una
pregunta general y una virtud para una específica, así que se controla con un
parámetro, no con una regla.

## Cómo se mide: como lo mide el curso, más un atajo para iterar

El curso (rama `session_16`) ya resolvió esto y esta propuesta lo sigue:

- **`evals/golden_retrieval.json`** — un golden set **anotado a mano**, donde cada
  pregunta lleva los documentos que son genuinamente relevantes, y **distractores
  deliberados**: documentos "parecidos pero irrelevantes".
- **`scripts/eval_retrieval_s10.py`** — reporta **precision@k** (`hits / k`) y
  latencia, comparando **configuraciones con nombre** una al lado de la otra.

Vale la pena citar para qué armaron ese golden set, porque nombra los tres fallos
que yo medí acá por separado:

> *"averaged multi-topic queries, the dominant collection flooding the top-k,
> **lexical identifiers diluted by embeddings**"*

El tercero es exactamente el caso `CAC011`, y el segundo es la concentración en un
solo documento. No estoy proponiendo una arquitectura nueva: estoy reconstruyendo
la del curso sobre este corpus, y los fallos coinciden.

### El golden set lo tiene que revisar alguien que conozca el negocio

Anotar a mano es el punto: un golden set escrito solo por el modelo que después se
evalúa contra él es un número que no se sostiene. Lo que se hace acá es
**borradorear** 20-30 preguntas a partir de secciones reales del corpus
(`Función general`, `Validaciones`, `Requisitos`) con su documento esperado, y
dejarlas para revisión antes de reportar nada.

### Y un proxy gratis, para iterar mientras se ajusta la fusión

1.871 documentos tienen título **único**, lo que da un conjunto etiquetado sin
anotar nada: el título como consulta, ese documento como respuesta. Como hay
exactamente un documento correcto por consulta, la métrica es una **tasa de
acierto** en los primeros k.

Línea base con la búsqueda vectorial actual, muestra de 60:

| | |
|---|---:|
| acierto@1 | **70%** |
| acierto@5 | **88%** |
| acierto@10 | **92%** |

**Es un proxy y NO reemplaza al golden set.** Un título no es una pregunta, y la
métrica premia parecerse al título. Su valor es que corre en segundos: sirve para
ver si un cambio en la fusión mejora o empeora mientras se itera, no para
reportar la calidad del sistema. Su techo tampoco es 100%: 349 documentos
comparten título con otro, y `VIC014_k` "falla" devolviendo `SGC001_k`, que tiene
el título **idéntico**.

Los dos números conviven: el proxy para iterar, precision@k sobre el golden set
para reportar.

## What Changes

- **`app/generation/rag/retrieval/`** — tres caminos y su fusión:
  - **vectorial**: el que ya existe, por coseno.
  - **léxico**: full-text en español, con semántica **OR ponderada** y no AND, y
    `ts_rank_cd` para rankear.
  - **exacto**: para identificadores (`CAC011`, `premium_mo`, `10208`), que la
    tokenización del full-text destroza. Por `document_id`, `field` y coincidencia
    literal.
- **Fusión por Reciprocal Rank Fusion, sin pesos por rama.** `k = 60`, el mismo
  constante del curso (Cormack et al.). La distancia coseno y el `ts_rank_cd` no
  son comparables ni normalizables de forma estable; RRF combina **posiciones**,
  no puntajes, y no calibra nada. **Sin pesos**: el curso deliberadamente no los
  tiene, y meterlos reintroduce la calibración manual que RRF justamente evita.
- **Diversidad opcional**, como tope de chunks por documento. Parámetro, con
  default que no la fuerza.
- **`GET /search`** — la primera consulta que el servicio expone.
- **`evals/golden_retrieval.json`** — el golden set, borradoreado del corpus y
  **pendiente de revisión** antes de reportar nada, con distractores deliberados.
- **`scripts/eval_retrieval.py`** — precision@k y latencia por configuración con
  nombre, como el `eval_retrieval_s10.py` del curso.
- **`scripts/eval_retrieval_proxy.py`** — la tasa de acierto sobre los títulos
  únicos, para iterar en segundos.

## Capabilities

### Capability nueva

- `retrieval`: encontrar los chunks relevantes a una consulta combinando
  similitud, léxico e identificador exacto.

## Impact

- `app/generation/rag/retrieval/{__init__,hybrid.py,fusion.py}` — nuevos.
- `app/generation/rag/store/repository.py` — los dos métodos de búsqueda nuevos.
- `app/api/search.py`, `app/main.py` — el endpoint.
- `app/config.py` — pesos de fusión, tope por documento, `k` por camino.
- `alembic/` — una migración para `pg_trgm` y su índice, si el camino exacto lo
  necesita.
- `scripts/eval_retrieval.py` — nuevo.

## Lo que este cambio NO hace

- **No genera respuestas.** Devuelve chunks con su procedencia. La generación
  —prompt, llamada al LLM, citas— es la capability siguiente.
- **No hace reranking, ni transformación de consulta, ni ruteo.** El curso tiene
  las tres (`retrieval/reranker.py`, `query_transform.py`, `router.py`) y este
  cambio ninguna. Cada una mejora el resultado y cuesta una llamada más por
  consulta; el orden sensato es medir cuánto da la fusión sola —con la métrica ya
  puesta— y recién entonces agregar. Quedan nombradas para que no se pierdan.
- **No arma el mapa de procesos.** Quedó planteado al principio del proyecto
  (relacionar transacciones entre sí para un CAG) y sigue pendiente; necesita las
  `references` que el chunker ya extrae, y es su propio cambio.

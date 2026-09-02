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

## Se puede medir, y hay una línea base

1.871 documentos tienen un título **único** [VERIFICADO-CORPUS]. Eso da un
conjunto etiquetado gratis: usar el título como consulta y esperar que vuelvan
los chunks de ese documento.

Línea base con la búsqueda vectorial actual, sobre una muestra de 60:

| | |
|---|---:|
| recall@1 | **70%** |
| recall@5 | **88%** |
| recall@10 | **92%** |

No está saturado, así que sirve para comparar antes y después.

**Es un proxy, no la verdad del dominio.** Un título no es una pregunta real, y
la métrica premia parecerse al título. Sirve para saber si un cambio mejora o
empeora la recuperación; no para afirmar que la recuperación es buena. La
evaluación con preguntas reales necesita a alguien que conozca el negocio, y eso
queda anotado, no simulado.

## What Changes

- **`app/generation/rag/retrieval/`** — tres caminos y su fusión:
  - **vectorial**: el que ya existe, por coseno.
  - **léxico**: full-text en español, con semántica **OR ponderada** y no AND, y
    `ts_rank_cd` para rankear.
  - **exacto**: para identificadores (`CAC011`, `premium_mo`, `10208`), que la
    tokenización del full-text destroza. Por `document_id`, `field` y coincidencia
    literal.
- **Fusión por Reciprocal Rank Fusion.** La distancia coseno y el `ts_rank_cd` no
  son comparables ni normalizables de forma estable; RRF combina **posiciones**,
  no puntajes, y no tiene que calibrar nada.
- **Diversidad opcional**, como tope de chunks por documento. Parámetro, con
  default que no la fuerza.
- **`GET /search`** — la primera consulta que el servicio expone.
- **`scripts/eval_retrieval.py`** — recall@k sobre los 1.871 documentos de título
  único, para que "mejoró" sea un número.

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
- **No hace reranking con un modelo.** Un cross-encoder mejora el orden y cuesta
  una llamada por consulta; primero hay que ver cuánto da la fusión sola, con la
  métrica ya puesta.
- **No arma el mapa de procesos.** Quedó planteado al principio del proyecto
  (relacionar transacciones entre sí para un CAG) y sigue pendiente; necesita las
  `references` que el chunker ya extrae, y es su propio cambio.

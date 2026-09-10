# Diseño

Cuatro decisiones que un lector futuro, si no, preguntaría por qué.

## 1. Este change muestra; no recorta

`add-window-status-metadata` dejó el filtro fuera con una frase
que se lee fácil como "la consola lo hace": *excluir lo no
contemplado es una decisión de producto que necesita la consola
web*. Lo que necesita la consola es **ver** el estado para poder
decidir. Recortar es otra decisión, y el contrato no está.

`GET /search` acepta `module_code` y `window_type_name` repetidos.
No acepta `window_status`. FastAPI ignora query params que el
endpoint no declara: un `MultiSelectFilter` que mande
`?window_status=Activo` volvería los mismos hits que sin filtro, y
el operador leería "solo vigentes" sobre 570 documentos de acceso
restringido. Eso es peor que no tener filtro.

**Por eso el filtro no entra acá.** El change siguiente es
`add-window-status-filter` en `-ai-service` (`SearchFilters`,
query param, facets, el mismo campo en `AnswerRequest`) y un
espejo web que reenvía de verdad. Hasta entonces, el default
sigue siendo el de hoy: todos los hits, con el estado a la vista.

**Alternativa descartada:** default "solo Activo" en la UI sin
param. Mentiría el recorte o, si filtrara en el cliente sobre los
10 hits ya rankeados, dejaría huecos y escondería evidencia que el
modelo sí vio. El recorte tiene que ser predicado de la consulta,
como ya es `module_code`.

## 2. El badge solo aparece cuando hay algo que advertir

`render_hit_block` agrega la línea de estado **solo si** está
resuelto y no es `Activo`. Un hit vigente o sin estado sale byte a
byte igual que antes, y el eval de fidelidad sigue siendo
comparable. La consola copia esa regla: un mar de badges "Activo"
no informa, y un badge "sin estado" convertiría la ausencia en un
valor del catálogo, que es justo lo que la spec de metadata
prohíbe (*ningún consumidor DEBE interpretar esa ausencia como
"activo"*, y tampoco como un cuarto estado inventado).

El texto del badge es el nombre declarado (`Acceso restringido`,
`En proceso de instalación`). Nunca "baja": el catálogo no dice
eso.

**Alternativa descartada:** pintar siempre el estado, incluido
`Activo`. Perdió por ruido. Tres estados reales en el corpus
(medido: 21.352 / 20.995 / 338 chunks); el vigente es la mayoría
de lo que un operador da por sentado.

## 3. Un componente, no tres copias de la regla

Búsqueda, citas del chat y vista previa de ingesta tienen que
aplicar **la misma** condición. El estándar de frontend pide no
extraer un control compartido hasta que tres pantallas copien el
patrón; este change **son** esas tres. `WindowStatusBadge` vive en
`components/` (no en `lib/ai-service/`: eso es `server-only` y
rompería el build si un Client Component lo importara).

`CitationSnapshot` no entra. El transcript durable guarda
procedencia mínima (documento, sección, hash) y **no** el texto
del chunk ni los scores; el estado de la ventana es del retrieve
que produjo el turno, no del registro de lo citado. Inventarlo al
reabrir sería el mismo defecto que inventar tokens en
`add-llm-usage-console`. Si más adelante el snapshot lo trae, el
badge ya acepta `undefined` y empieza a pintarse sin otro change
de UI.

## 4. No se hardcodea el catálogo en la consola

`WINDOW_STATUSES` vive en `navigation.py` y sale de `TABLE26`.
Copiar los tres nombres en el frontend crearía una segunda fuente
de verdad que se desincroniza el día que el catálogo sume un
valor. Como este change no ofrece un listado para elegir, no
necesita la lista: pinta lo que el hit trae. El día del filtro,
las opciones salen de `GET /search/facets` (valores distintos
presentes en el corpus), no de un array escrito en el cliente —
el mismo patrón que `module_code` y `window_type_name`.

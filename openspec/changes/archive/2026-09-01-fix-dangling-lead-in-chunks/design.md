# Diseño || Design

## El problema, en una línea

El corpus tiene jerarquía de listas; el chunker no la ve, porque la jerarquía
está escrita con los glifos que Word usa para sus niveles de viñeta (`·`, `o`,
`§`) y no con markdown. Todo lo que el chunker ve es una secuencia plana de
párrafos separados por línea en blanco.

## Las alternativas, y por qué perdieron

### A. Filtrar por largo

Descartada antes de este cambio y por escrito: habría borrado 291 respuestas
reales (`No aplica.`, `A petición del usuario.`). No se reabre. Además no
sirve acá: el lead-in grave (`· De la tabla de Situación impositiva del Cliente
(ClientTaxSitua) se obtiene:`) es largo.

### B. Borrar los conectores puros por lista de palabras

`De lo contrario,`, `Dónde,`, `En el detalle:`. Son 109 de 1.058. Aun si la
lista fuera perfecta, **borrarlos empeora el problema**: el conector es el
único indicio de que el chunk siguiente es la rama contraria. Sin él, la
inversión pasa de detectable a invisible. Y viola la regla de no borrar
información de negocio en silencio.

### C. Dar profundidad a `·` / `o` / `§` y reusar la regla de bullets

La opción arquitectónicamente elegante: si `_BULLET_LINE` reconociera esos
glifos con un orden de anidamiento, la regla existente ("un bullet de primer
nivel con todos sus hijos = un chunk") resolvería el condicional entero sin
código nuevo.

**Se midió, y el glifo no es un indicador confiable de profundidad.**

Frecuencia en el corpus fuente (2171 archivos) [VERIFICADO-CORPUS]:
`·` 4867, `o` 3078, `§` 2149.

Transiciones lead-in→hijo (el hijo tiene que ser más profundo que su lead-in),
contadas sobre los 1.065 pares reales [VERIFICADO-CORPUS]:

| Transición | Veces | Inversa | Veces |
|---|---|---|---|
| `·` → `o` | 105 | `o` → `·` | 7 |
| `o` → `§` | 83 | `§` → `o` | 2 |
| `§` → `·` | **43** | `·` → `§` | 5 |

Las dos primeras filas son consistentes con el orden por defecto de las listas
multinivel de Word (`•`, `o`, `§`) y sostienen `·` > `o` > `§`
[VERIFICADO-CORPUS: 12 documentos exhiben ambos descensos]. La tercera lo
rompe: `§` → `·` con 43 casos, concentrados en 4 documentos
(`INSCALCSTAMPTAX`, `INSCALGROSSEARN`, `INSCALRETIIBB_RG`,
`INSROUTINEANNULMENT`), que usan una asignación de niveles distinta
[VERIFICADO-CORPUS].

Precisión de las dos reglas de profundidad candidatas, evaluadas contra los
pares lead-in→hijo, que por construcción tienen que descender
[VERIFICADO-CORPUS]:

| Regla | Acierta | Falla | Precisión |
|---|---|---|---|
| Orden global `·` > `o` > `§` | 193 | 52 | **78,8%** |
| Orden por primera aparición en la sección | 187 | 58 | **76,3%** |

Un 21% de pares mal anidados significa 1 de cada 5 hijos colgando del padre
equivocado — que es exactamente la inversión de la regla de negocio que este
cambio existe para evitar. **Una jerarquía que acierta 4 de 5 veces es peor que
no tener jerarquía**, porque produce chunks que *parecen* completos y afirman
lo contrario de lo que dice el documento.

Queda como trabajo futuro con otra evidencia: la profundidad de blockquote
(`>`, `> >`) es una señal independiente que el export también emite, y podría
desempatar. No se usa acá porque no está medida.

### D. Unir hacia adelante por gramática (elegida)

No necesita saber nada de la jerarquía. Una unidad cuyo texto termina en `,` o
en `:` no cerró su enunciado; el enunciado sigue en la unidad siguiente de la
misma sección. Unirlas restaura el condicional completo — condición, rama
`then`, conector, rama `else` — en un solo chunk, sin decidir quién es padre de
quién.

Propiedades que la hacen preferible a C:

- **Es local y verificable.** El criterio se lee del propio texto del chunk; no
  depende de una calibración de glifos por documento.
- **No puede invertir nada.** Unir dos unidades adyacentes preserva el orden del
  fuente. El peor caso es un chunk más grande de lo ideal, no uno que miente.
- **Cubre el caso que C no cubre.** `De lo contrario,` no lleva glifo: en el
  fuente de `PRODUCERS_AGL009` es una línea pelada entre un `§` y un `·`.
  Ninguna regla de profundidad de glifos la ve. La regla gramatical sí.
- **Entra bajo el techo.** 94,4% de los 954 grupos quedan bajo los 500 tokens
  [VERIFICADO-CORPUS].

## El residuo: 53 grupos que no entran bajo el techo

Unir a la fuerza rompería la garantía de `token_count` ≤ cap, que la capa de
embeddings verifica antes de la primera llamada a la API. Partir por oraciones
volvería a colgar el enunciado.

Se aplica el principio que este repo ya usó con los documentos índice y con las
tablas rotas: **marcar o recuperar, nunca borrar**. Los chunks se emiten
separados, y cada uno declara su vecino:

- `continued_from: "<chunk_id>"` — el enunciado de este chunk empieza en ese otro.
- `continues_into: "<chunk_id>"` — el enunciado de este chunk termina en ese otro.

Ambos opcionales y ausentes por defecto, como el resto de la metadata opcional
del schema: ausente se lee como "no aplica", nunca como vacío. El retrieval
puede traer el vecino cuando recupera uno de los dos; esa decisión es de la
capa de retrieval y no se toma en este cambio.

## Por qué el criterio no es una lista de conectores

Se consideró detectar `De lo contrario`, `En caso contrario`, `Dónde`, etc. Es
un diccionario cerrado sobre un corpus de 30 módulos con redacción libre — el
mismo error que la spec de `chunk_id` ya documenta para las traducciones de
headings: "un diccionario fijo falla en silencio con cada heading nuevo". La
puntuación final es una propiedad del castellano, no del corpus.

Falso positivo conocido y aceptado: un chunk que legítimamente termina en `:`
porque el `:` es el último carácter de una enumeración que el export truncó. Se
une con el siguiente y el chunk queda un poco más largo. Es un costo de
tamaño, no de corrección.

## Qué se rompe

Los `content_hash` de los 1.964 chunks afectados cambian, porque cambia el
`text`. La capa de embeddings los vuelve a pedir a la API en la próxima corrida
—unas 2.000 llamadas de las 61.901 filas— y descarta las filas viejas cuyo hash
ya no está en el corpus. Es el camino incremental funcionando como fue
diseñado. El corpus completo NO se re-embebe.

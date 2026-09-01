## Why

Al deduplicar por `content_hash` en la capa de embeddings aparecieron chunks
que `carries_no_information()` no atrapa porque **sí** tienen texto — pero el
texto es un enunciado colgado, no una afirmación:

```
[Documento: PRODUCERS_AGL009 - ...]
[Sección: Proceso batch]
De lo contrario,
```

Ese chunk se emitió 72 veces. No es ruido de formato: es la mitad de una regla
de negocio. En el fuente, `De lo contrario,` separa las dos ramas de un
condicional de cálculo de retenciones:

```
§Si el importe de ajuste ... es mayor al importe de Comisión Neta ...
·Se calcula como ajuste ... el importe de Comisión Neta ...
De lo contrario,
·Se calcula como ajuste ... el importe de ajuste por mínimo de retención ...
```

El chunker emite esas cuatro unidades como cuatro chunks. El resultado no es
que sobre un chunk vacío — es que **la rama `else` queda indistinguible de la
rama `then`**. Un `·Se calcula...` recuperado solo se lee como la consecuencia
de la condición, cuando es su contraria. Es exactamente la inversión que la
spec ya declara inaceptable para los bullets markdown ("un hijo NUNCA debe
separarse de su padre, porque una condición anidada leída sin su padre invierte
la regla de negocio") — pero el corpus no usa bullets markdown acá: usa los
glifos `·`, `o`, `§` que el export de Word emite, y `_BULLET_LINE` solo
reconoce `*`, `-`, `+`. Para el chunker esa jerarquía no existe: son párrafos
sueltos separados por línea en blanco.

**Medición sobre el corpus** (`data/chunks/*.json`, 61.901 chunks, 2250
documentos) [VERIFICADO-CORPUS]:

| | Chunks | % del corpus |
|---|---|---|
| Chunks narrativos | 32.678 | 52,8% |
| ...cuyo texto termina en `,` o `:` — **enunciado colgado** | 1.058 | 1,71% |
| ...que son el chunk inmediatamente siguiente a uno colgado | 1.036 | 1,67% |
| **Unión (un lado u otro de un enunciado partido)** | **1.964** | **3,17%** |
| Documentos afectados | 253 de 2250 | 11,2% |

De los 1.058 enunciados colgados, 109 son conectores puros sin información
propia (`De lo contrario,`, `Dónde,`, `En el detalle:`) y **949 son
lead-ins con contenido** — el caso grave, porque la condición se pierde:

```
LEAD-IN : "· De la tabla de Situación impositiva del Cliente (ClientTaxSitua) se obtiene:"
ORPHAN  : "o La condición ante el IVA (nVatSituation). La descripción se obtiene de ..."
```

El costo no es de dinero: la capa de embeddings ya deduplica por
`content_hash`, así que `De lo contrario,` se paga una sola vez. El costo es de
recuperación y de corrección: 1.964 chunks que se recuperan sin la mitad de su
enunciado, y un subconjunto que se recupera con el sentido invertido.

## What Changes

- **El discriminador es gramatical, no de largo.** Una unidad narrativa cuyo
  texto termina en `,` o `:` no es una afirmación completa: continúa en lo que
  sigue. Ese criterio no toca `No aplica.` ni `A petición del usuario.` — las
  291 respuestas reales cortas que el filtro por largo habría borrado y que la
  spec ya protege — porque esas terminan la oración.
- **Se une hacia adelante, no se borra.** La unidad colgada se junta con las
  que siguen en la misma sección hasta cerrar el enunciado, respetando el techo
  de tokens. Lo que se reconstruye es el ENUNCIADO: `De lo contrario,` viaja
  con la rama que introduce, y un lead-in viaja con lo que cierra su oración.
  La condición `§Si <cond>.` de más arriba, que cierra con punto, sigue en su
  propio chunk — pegarla exigiría la jerarquía de glifos que se midió y se
  descartó (78,8%, ver `design.md`).
- **Cuando la unión no entra bajo el techo, se MARCA.** El chunk se emite igual
  y declara en su metadata `continues_into` / `continued_from` con el
  `chunk_id` del vecino. Nunca se descarta: es el mismo principio que hizo
  marcar los documentos índice en vez de tirarlos.
- **`carries_no_information()` no cambia.** Sigue siendo el filtro de
  estructura vacía. Un enunciado colgado sí lleva información — el defecto es
  que está partida, y partida se repara uniendo, no filtrando.

**Efecto medido de la unión** (simulación sobre los chunks actuales)
[VERIFICADO-CORPUS]:

| | |
|---|---|
| Grupos lead-in + continuación | 954 |
| Chunks que absorben | 2.020 → 954 |
| Reducción neta del corpus | −1.066 chunks (−1,72%) |
| Grupos que entran bajo el techo de 500 tokens | 901 (**94,4%**) |
| Grupos que exceden el techo → se marcan, no se unen | 53 (5,6%) |

## Resultado medido tras implementar

Corrida completa del chunker sobre los 2169 archivos del corpus, comparada
contra `data/chunks` generado antes del cambio [VERIFICADO-CORPUS]:

| | Antes | Después |
|---|---|---|
| Chunks del corpus | 61.901 | **60.451** (−1.450, −2,34%) |
| Chunks con enunciado abierto | 1.090 | **92** (−91,6%) |
| ...enlazados con `continues_into` | — | 70 |
| ...última unidad de su sección, sin nada adelante | — | 22 |
| Documentos afectados | 253 | 61 |
| Documentos que perdieron todos sus chunks | — | **0** |
| Chunks narrativos sobre el techo de 500 | 0 | **0** |
| Enlaces que apuntan a un chunk inexistente | — | **0** |

Los 22 sin enlace son legítimos: son la última unidad de su sección y no hay
nada adelante a lo cual unirlos. Varios son truncamientos del propio export —
`op714.md` termina su sección `Efecto` con “...estado “Pendiente de
aprobación,”, sin cerrar la oración en el fuente.

## Capabilities

### Modified Capabilities

- `document-chunking`: la segmentación narrativa une hacia adelante la unidad
  que deja un enunciado colgado, en vez de emitirla sola.
- `chunk-schema`: `ChunkMetadata` gana `continued_from` / `continues_into`,
  opcionales, para el caso en que la unión no entra bajo el techo.

## Impact

- `app/generation/rag/chunking/functional_spec.py` — `_segment_prose`
  (unión hacia adelante) y `_chunk_narrative_section` (marcado del residuo).
- `app/generation/rag/schemas.py` — dos campos opcionales en `ChunkMetadata`.
- `tests/generation/rag/chunking/` — casos del corpus real como fixtures.
- `data/chunks/` — artefacto regenerado; los `content_hash` de los 1.964 chunks
  afectados cambian, así que la próxima corrida de embeddings los vuelve a
  pedir. Es el comportamiento correcto de la capa incremental, no un defecto.

## Lo que este cambio NO hace

- **No le da profundidad a `·` / `o` / `§`.** La alternativa obvia era tratar
  esos glifos como bullets con un orden de anidamiento y dejar que la regla de
  "bullet con sus hijos" existente resolviera todo. Se midió y **no alcanza**:
  el glifo predice la profundidad correcta en ~79% de los pares lead-in→hijo.
  Un 21% mal anidado es precisamente la inversión que se está tratando de
  evitar. El detalle está en `design.md`.
- **No toca MER001** (`No` × 51) ni CAL013, los otros dos ejemplos que
  dispararon esta investigación. No son este defecto:
  - **MER001** es una tabla de 4 columnas que el export dejó sin pipes y que
    `table-repair` no reconoce: sus 191 chunks de `Valores definidos` son las
    celdas sueltas de ~48 filas, y `No` es la columna *Temporal*. Va en su
    propio cambio: `fix-unpiped-field-table-shape`.
  - **CAL013** es un **falso positivo**: el chunk repetido 23 veces es una fila
    de tabla completa y correcta (`Transacción: / Archivo de la base de datos:
    Policy_win / Creación...`) que el documento repite de verdad, una vez por
    secuencia de ventanas. La capa de embeddings la deduplica y eso es todo lo
    que hacía falta.

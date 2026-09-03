## Why

Sobre una pregunta real (*"¿VisualTIME administra reaseguro proporcional y no
proporcional?"*), 6 de los 10 resultados eran fragmentos de navegación
(`*_INDEX`, `*_INTRO`) —una sola línea de tabla de contenidos, sin información
sustantiva— cuando `document_kind='index'` es apenas **0,8% de los chunks y
1,6% de los documentos** del corpus. Sobrerrepresentados 4-8x.

Y dos de esos diez resultados eran texto **byte-idéntico** entre documentos
hermanos (`REINSURANCE_INTRO` / `REINSURANCE_REPORTS_INTRO`): con `cap=1` cada
uno cuenta como un "documento" distinto, así que dos lugares se gastan en una
sola oración repetida.

`document_kind` existe en el esquema con este propósito explícito desde que se
escribió: *"marca un nodo de navegación para que el retrieval lo pueda
despriorizar"*. Nunca se conectó — solo existe como filtro binario opcional que
ningún llamador activa.

## What Changes — y lo que NO cambia

Se implementaron dos mecanismos, **parametrizados y medidos, y NINGUNO de los
dos queda activado por default**: medidos contra las 35 preguntas humanas del
golden set, los dos dan pérdida neta.

### `index_penalty`: multiplica el puntaje RRF de un candidato 'index'

Medido contra 85 pares, sin reranker ni descomposición, para aislar el efecto
[VERIFICADO-CORPUS]:

| config | top10 | rango | perdidos | p@10 | `SI001_A` | `DP003_A` |
|---|---:|---:|---:|---:|---:|---:|
| **sin cambios** | **50** | 18 | 17 | **0,143** | 12 | **5** |
| `penalty=0,5` | 49 | 19 | 17 | 0,140 | 23 | **39** |
| `penalty=0,1` | 49 | 19 | 17 | 0,140 | 24 | **56** |

**No mejora nada en el agregado con ninguna magnitud**, y el motivo es exacto:
`SI001_A` y `DP003_A` —dos respuestas reales, anotadas por una persona— SON
documentos `index`. `DP003_A` estaba en el **puesto 5** (dentro del top-10) sin
tocar nada, y cae al puesto 34-58 con cualquier penalización. Es la única causa
del retroceso agregado: un documento que hoy responde bien, roto por el cambio.

La lectura de una sola consulta —*"6 de 10 son navegación, eso está mal"*— era
correcta como observación puntual y **equivocada como generalización**.

### `dedupe_text`: descarta un candidato cuyo cuerpo (sin el header) ya apareció

Mismo barrido, `penalty=1.0` (sin democión) + `dedupe_text=True`:

| config | top10 | rango | perdidos | p@10 |
|---|---:|---:|---:|---:|
| sin cambios | 50 | 18 | **17** | 0,143 |
| dedupe solo | 49 | 17 | **19** | 0,140 |

`perdidos` sube: **dos pares que estaban en el candidato de 60 dejan de
estarlo.** Diagnosticado con precisión contra la base [VERIFICADO-CORPUS]:

- `CAC1005B` (anotado relevante) se pierde; sobrevive `CAC1005A`, cuerpo
  idéntico.
- `CAC1006` (anotado relevante) se pierde; sobrevive `CAC1006B`, cuerpo
  idéntico.

El defecto es de diseño y no de implementación: el dedup confunde **"texto
idéntico"** con **"documento intercambiable"**. `CAC1005A`/`CAC1005B` y
`CAC1006`/`CAC1006B` son genuinamente documentos hermanos casi
intercambiables —hay una nota ya escrita en `evals/golden_curated.json` sobre
exactamente esta familia de códigos— pero el golden set anota por
`document_id` **exacto**, y un usuario real que pregunta por `CAC1005B`
específicamente recibiría `CAC1005A` en su lugar, en silencio, sin ninguna
señal de que hubo un swap.

## Lo que SÍ queda

- `document_kind` viaja ahora hasta `RetrievedChunk` y se expone en
  `SearchHit` de `/search`. Es dato de procedencia real —coherente con el
  propósito ya escrito del endpoint, *"todo lo necesario para VERIFICAR la
  respuesta"*— y no cambia ningún comportamiento por sí solo.
- `_demote_index_kind()` y `_dedupe_by_text()` quedan en el código,
  parametrizadas, con 12 tests unitarios que fijan que hacen lo que dicen
  hacer **cuando se activan**. Apagadas por default
  (`index_penalty=1.0`, `dedupe_text=False`), que es el único valor que la
  medición sostiene hoy.
- Ninguno de los dos parámetros se expone en `GET /search`: exponer un knob
  cuyo único valor medido es "no lo uses" sería agregar superficie sin
  ninguna razón.

## Impact

- `app/generation/rag/store/repository.py`: `document_kind` en `_SELECTED`,
  `SearchHit`, `RankedHit`.
- `app/generation/rag/retrieval/hybrid.py`: `_demote_index_kind()`,
  `_dedupe_by_text()`, `_body_of()`, parámetros `index_penalty`/`dedupe_text`
  en `retrieve()` y `_fuse_branches()`.
- `app/generation/rag/schemas.py`, `app/api/search.py`: `document_kind`
  expuesto en `SearchHit`.
- 12 tests unitarios nuevos, 0 tests rotos.
- Sin cambio de comportamiento en producción: los dos nuevos parámetros
  entran apagados.

## Lo que queda pendiente, con más precisión que antes

El problema original —6 de 10 lugares gastados en navegación para una
pregunta puntual— **sigue sin resolverse**. Lo que se descarta es
específicamente ESTA forma de resolverlo. Caminos que no se midieron todavía:

- Democión aplicada **solo cuando hay suficiente contenido real compitiendo**
  (no cuando 'index' es la mejor o única evidencia, que es el caso de
  `SI001_A`/`DP003_A`).
- Dedup que fusione candidatos hermanos en vez de descartar uno —sumando sus
  ramas y quedándose con AMBOS ids en la respuesta— en lugar de que uno
  desaparezca del todo.

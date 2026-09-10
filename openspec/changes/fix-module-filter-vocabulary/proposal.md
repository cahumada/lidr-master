## Why

**En el camino agéntico, nombrar una transacción recupera cero evidencia.**

Medido contra el servicio local el 2026-09-10:

| pregunta | filtro efectivo | citas |
|---|---|---:|
| `¿Qué valida CA014?` | `module_code=["CA"]`, origen `question` | **0** |
| `¿Qué valida el tratamiento de pólizas?` | ninguno | 5 |

La causa es de **vocabulario**. Dos productores de filtros creen que un módulo
se llama con dos a cuatro letras:

- `_suggest_filters` ([query_planner.py](../../../ai-service/app/domain/graph/agents/query_planner.py))
  toma el prefijo de un código con forma de transacción: `CA014` → `"CA"`.
- `_MODULE` ([anchors.py:60](../../../ai-service/app/generation/conversation/anchors.py))
  captura `\bm[óo]dulo\s+([A-Za-z]{2,4})\b`: «solo módulo CA» → `"CA"`.

Pero los `module_code` que el corpus realmente tiene son los códigos del **nodo
módulo del árbol `WINDOWS`**: `DMECAR`, `DMECLI`, `DMECOB`, `DMEMAN`… **17
valores, y ninguno de dos a cuatro letras.** Los dos productores emiten un
vocabulario que no existe, así que el filtro recorta a un módulo inexistente y
la búsqueda devuelve nada.

Y el caso del anchor es peor que el de la heurística: *«de acá en adelante, solo
módulo CA»* fija una restricción que **envenena todos los turnos siguientes** de
esa conversación. El usuario pidió el filtro; el servicio se lo aplica; nada
vuelve nunca más.

Estuvo así en producción y era invisible: hasta
`fix-dropped-agentic-filters` nada decía qué filtro se había aplicado ni de
dónde venía. Ese change lo hizo visible, y esto es lo que se vio.

### Por qué no alcanza con traducir el prefijo al módulo real

Es la salida obvia y **está medida y descartada**. El mapeo prefijo → módulo no
es una función: de 71 prefijos distintos del corpus, muchos caen en varios
módulos.

| prefijo | módulos | reparto |
|---|---:|---|
| `OPL` | 5 | `DMECOB`:608, `DMECYB`:444, `DMEBOOK`:140, `DMECAR`:130 |
| `MA` | 4 | `DMEMAN`:3399, `DMEOS`:25, `DMEDIS`:7, `DMECAR`:2 |
| `AGL` | 3 | `DMEINT`:2025, `DMEBOOK`:135, `DMECAR`:47 |
| `CAC` | 2 | `DMECAR`:3104, `DMECOB`:40 |

Elegir el módulo dominante dejaría afuera la cola —40 chunks de `CAC` en
`DMECOB`, 25 de `MA` en `DMEOS`— y eso es pérdida silenciosa de información de
negocio, que es justamente lo que las reglas del repo prohíben.

## What Changes

- **Se quita el filtro derivado de la pregunta.** No se pierde ningún
  comportamiento que funcione: nunca matcheó. Y el camino de coincidencia exacta
  de `retrieval` ya existe para que una consulta que nombra `CA014` lo encuentre
  por `document_id` — filtrar además por módulo solo puede restar.
- **«módulo CA» se resuelve como lo que el usuario quiere decir**: las
  transacciones cuyo código empieza con `CA`. Es una **dimensión distinta** de
  `module_code`, se aplica sobre `document_id`, y no adivina nada. La palabra
  «módulo» significa dos cosas distintas para la persona y para el corpus, y
  este change deja de forzar una sobre la otra.
- **Un valor fuera de su vocabulario NUNCA se aplica en silencio.** Si no se
  puede resolver, no se filtra y se reporta — un filtro que nadie puede ver es
  el defecto que este change cierra, y la regla tiene que sobrevivir a la
  próxima heurística que alguien agregue.
- El vocabulario de `module_code` queda declarado como lo que es: los códigos
  del nodo módulo de `WINDOWS`, los mismos que sirve `GET /search/facets`.

Fuera de alcance:

- **Mapear prefijo → módulo.** Medido y descartado arriba.
- **Un control de prefijo en la consola.** El selector de módulo ya manda el
  vocabulario correcto desde las facets. Ofrecer además un filtro por prefijo es
  un change de `web`.

## Capabilities

### Modified Capabilities

- `answer-orchestration`: se quita la fuente `question` de los filtros, el
  anchor de módulo se resuelve por prefijo de transacción, y un valor
  irresoluble se reporta en vez de aplicarse.
- `conversation-memory`: qué fija un anchor de módulo y contra qué se aplica.

## Impact

- `ai-service/app/domain/graph/agents/query_planner.py` — se va
  `_suggest_filters`; la resolución queda con dos fuentes.
- `ai-service/app/generation/conversation/anchors.py` — el anchor de módulo pasa
  a ser un prefijo de transacción, no un `module_code`.
- `ai-service/app/generation/conversation/models.py` — el `kind` del anchor.
- `ai-service/app/generation/rag/store/repository.py` — el filtro por prefijo de
  `document_id`.
- `ai-service/app/domain/schemas.py` — el campo del filtro nuevo.
- `ai-service/tests/` — tests, incluida la reproducción medida.
- `openspec/specs/retrieval/spec.md` — solo si el filtro nuevo cambia lo que esa
  spec afirma sobre el recorte previo al ranking.

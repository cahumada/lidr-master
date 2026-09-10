# answer-orchestration Delta Specification

## MODIFIED Requirements

### Requirement: Los filtros del request DEBEN llegar al grafo, y su precedencia DEBE estar declarada
`AnswerRequest` lleva `module_code` y `window_type_name`, y los endpoints
agénticos DEBEN honrarlos: el estado semilla los transporta y el retriever los
aplica. Aceptarlos y descartarlos es el comportamiento silencioso que este
servicio no permite — y aceptarlos en un endpoint y no en otro, con el mismo
contrato, es peor todavía.

Hay **dos** fuentes de filtros y la precedencia es `request → anchor`: lo que el
operador eligió para este turno le gana al que fijó en un turno anterior, porque
el anchor es un default y no una jaula.

**Ya no existe una tercera fuente derivada del texto de la pregunta.** Emitía un
prefijo de transacción (`CA014` → `"CA"`) como si fuera un `module_code`, y los
`module_code` del corpus son los del nodo módulo de `WINDOWS` (`DMECAR`,
`DMECLI`, …): recortaba a un módulo inexistente y dejaba la pregunta sin
evidencia. La rama de coincidencia exacta de `retrieval` ya encuentra una
transacción nombrada por su `document_id`, así que ese filtro solo podía restar.

La resolución ocurre en **un solo nodo** (el planner). El retriever lee los
filtros ya resueltos y no conoce la política, que es lo que mantiene a
`search_corpus` en el mismo camino que `/search`.

Se resuelve **por campo**: un request que trae `module_code` y no
`window_type_name` no borra el tipo de ventana que un anchor aportó.

Y ningún valor se aplica fuera de su vocabulario: el de `module_code` son los
códigos que sirve `GET /search/facets`. Un valor irresoluble no se filtra y se
registra — un filtro que nadie puede ver es el defecto que esta regla cierra.

#### Scenario: El filtro del request recorta la búsqueda
- **WHEN** una corrida agéntica recibe `module_code` en el body
- **THEN** el retriever busca con ese filtro
- **AND** un valor que no corresponde a ningún módulo del corpus devuelve cero
  hits, en lugar de resultados sin recortar

#### Scenario: Nombrar una transacción no recorta por módulo
- **WHEN** la pregunta nombra una transacción y el body no trae filtros
- **THEN** no se aplica ningún filtro de módulo
- **AND** la transacción se encuentra por la rama de coincidencia exacta

#### Scenario: El request le gana al anchor
- **WHEN** el body pide un módulo y hay otro fijado en un turno anterior
- **THEN** se aplica el del body

#### Scenario: Un request parcial no borra las otras fuentes
- **WHEN** el body trae `module_code` y no `window_type_name`, y un anchor
  aporta un tipo de ventana
- **THEN** el módulo sale del body y el tipo de ventana del anchor

#### Scenario: Sin filtros en el request nada cambia
- **WHEN** el body no trae ninguno de los dos campos y no hay anchors
- **THEN** no se aplica ningún filtro

#### Scenario: Paridad entre los dos endpoints
- **WHEN** la misma pregunta con el mismo filtro se manda por `POST /answer` y
  por `POST /answer/agentic`
- **THEN** las dos recortan al mismo módulo

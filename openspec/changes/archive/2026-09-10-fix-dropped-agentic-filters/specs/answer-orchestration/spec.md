# answer-orchestration Delta Specification

## ADDED Requirements

### Requirement: Los filtros del request DEBEN llegar al grafo, y su precedencia DEBE estar declarada
`AnswerRequest` lleva `module_code` y `window_type_name`, y los endpoints
agénticos DEBEN honrarlos: el estado semilla los transporta y el retriever los
aplica. Aceptarlos y descartarlos es el comportamiento silencioso que este
servicio no permite — y aceptarlos en un endpoint y no en otro, con el mismo
contrato, es peor todavía.

Hay **tres** fuentes posibles para un filtro y la precedencia es
`request → pregunta → anchor`. La del medio es la única que no es una
declaración de intención: es una heurística que extrae códigos con forma de
transacción del texto de la pregunta. Un control que el operador eligió para
este turno le gana a esa inferencia, que a su vez sigue ganándole al filtro
fijado en un turno anterior — el anchor es un default, no una jaula.

La resolución ocurre en **un solo nodo** (el planner). El retriever lee los
filtros ya resueltos y no conoce la política, que es lo que mantiene a
`search_corpus` en el mismo camino que `/search`.

Se resuelve **por campo**: un request que trae `module_code` y no
`window_type_name` no borra el tipo de ventana que la pregunta o un anchor
aportaron.

#### Scenario: El filtro del request recorta la búsqueda
- **WHEN** una corrida agéntica recibe `module_code` en el body
- **THEN** el retriever busca con ese filtro
- **AND** un valor que no corresponde a ningún módulo del corpus devuelve cero
  hits, en lugar de resultados sin recortar

#### Scenario: El request le gana a la heurística de la pregunta
- **WHEN** el body pide un módulo y el texto de la pregunta nombra una
  transacción de otro
- **THEN** se aplica el del body

#### Scenario: La pregunta le gana al anchor
- **WHEN** hay un anchor de módulo fijado y la pregunta nombra explícitamente
  una transacción de otro módulo, sin filtro en el body
- **THEN** se aplica el de la pregunta

#### Scenario: Un request parcial no borra las otras fuentes
- **WHEN** el body trae `module_code` y no `window_type_name`, y un anchor
  aporta un tipo de ventana
- **THEN** el módulo sale del body y el tipo de ventana del anchor

#### Scenario: Sin filtros en el request nada cambia
- **WHEN** el body no trae ninguno de los dos campos
- **THEN** los filtros efectivos son los que el planner ya producía
- **AND** el comportamiento es idéntico al anterior a este cambio

#### Scenario: Paridad entre los dos endpoints
- **WHEN** la misma pregunta con el mismo filtro se manda por `POST /answer` y
  por `POST /answer/agentic`
- **THEN** las dos recortan al mismo conjunto de documentos

### Requirement: Los filtros efectivos DEBEN reportarse con su origen
Un filtro aplicado sin decirlo es un defecto, no una comodidad — y con tres
fuentes posibles, saber que se filtró no alcanza: hay que poder ver por qué.

La respuesta declara los filtros en vigor y de dónde salió cada valor
(`request`, `question` o `anchor`), del mismo modo que la configuración efectiva
de un agente declara si cada knob vino del perfil o de los settings. La
contribución del planner en `agent_contributions` registra lo mismo.

#### Scenario: El origen viaja en la respuesta
- **WHEN** una corrida aplica un filtro que vino del body
- **THEN** la respuesta declara ese filtro con origen `request`

#### Scenario: Un turno pausado también lo declara
- **WHEN** la corrida queda esperando revisión humana
- **THEN** el payload de pausa lleva los filtros efectivos y su origen, porque
  ya se aplicaron antes de llegar al gate

#### Scenario: La auditoría del planner nombra la fuente
- **WHEN** el planner resuelve filtros de más de una fuente
- **THEN** su fila de `agent_contributions` dice de dónde salió cada valor

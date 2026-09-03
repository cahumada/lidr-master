# answer-generation Delta Specification

## ADDED Requirements

### Requirement: POST /answer DEBE sintetizar una respuesta a partir de los chunks recuperados
El endpoint recibe una pregunta en lenguaje natural y los mismos filtros que
`GET /search` (`module_code`, `window_type_name`, más los knobs medidos del
pipeline). Corre el `HybridRetriever` existente —sin forkearlo—, arma un
prompt con el contexto recuperado, llama al LLM y devuelve la prosa más las
citas.

Las citas del contrato SON los `SearchHit` recuperados, no un segundo modelo
y no los marcadores que el LLM escribió en la prosa. Verificar una cita es
mirar `citations`, no parsear el texto.

#### Scenario: Pregunta con contexto suficiente
- **WHEN** `POST /answer` recibe una pregunta de al menos 2 caracteres y el
  retriever devuelve hits
- **THEN** la respuesta lleva `answer` (texto del LLM), `citations` igual a
  esos hits, y `question` tal como llegó

#### Scenario: Sin hits no se llama al LLM
- **WHEN** el retriever no devuelve ningún chunk
- **THEN** `answer` declara que no hay información suficiente
- **AND** `citations` está vacío
- **AND** `grounded` es true
- **AND** el LLM no se invoca

#### Scenario: Los filtros llegan al retriever
- **WHEN** el body lleva `module_code` o `window_type_name`
- **THEN** `HybridRetriever.retrieve` recibe un `SearchFilters` con esos
  valores, los mismos que usaría `/search`

#### Scenario: Una pregunta de un carácter se rechaza
- **WHEN** `question` tiene menos de 2 caracteres
- **THEN** el endpoint responde 422
- **AND** no hay una validación de entrada aparte: es el `min_length=2` del
  contrato, la misma regla que `Query(min_length=2)` en `/search`

### Requirement: Las citas de la respuesta DEBEN ser los chunks realmente recuperados
Un `document_id` que el LLM mencione no es una cita. La procedencia
verificable es `citations: list[SearchHit]`, el mismo modelo que `/search`,
para que no existan dos ideas de «cita» que puedan divergir.

#### Scenario: citations es el resultado del retriever
- **WHEN** el retriever devuelve tres hits
- **THEN** `citations` tiene esos tres, en el mismo orden, con
  `document_id`, `section`, `bullet_path` y `text`

#### Scenario: Un marcador inventado no entra en citations
- **WHEN** el LLM escribe `[ZZ999 · Función]` y el retriever no devolvió
  `ZZ999`
- **THEN** `citations` no incluye `ZZ999`

### Requirement: Una cita sin respaldo DEBE marcarse, no rechazarse
El guardrail de salida extrae de la prosa los marcadores
`[document_id · section]` y comprueba que cada `document_id` esté entre los
hits recuperados. Si alguno no está, `grounded` es false y la respuesta se
devuelve igual: `citations` sigue siendo la procedencia verificable, y
descartar la prosa impediría puntuarla.

#### Scenario: Todas las citas inline están en los hits
- **WHEN** la prosa cita `[CA014 · Validaciones]` y hay un hit de `CA014`
- **THEN** `grounded` es true

#### Scenario: Un document_id citado no está en los hits
- **WHEN** la prosa cita `[ZZ999 · Función]` y ningún hit tiene `ZZ999`
- **THEN** `grounded` es false
- **AND** el endpoint no responde 4xx

#### Scenario: Sin marcadores no hay alucinación de cita
- **WHEN** la prosa no contiene ningún `[document_id · section]`
- **THEN** `grounded` es true

### Requirement: El prompt DEBE instruir anclaje, citas y insuficiencia
El system prompt v1 dice tres cosas que el guardrail después puede
observar: responder solo con el contexto, citar cada afirmación como
`[document_id · section]`, y declarar que no hay información suficiente
cuando el contexto no alcanza. Cada chunk entra al user prompt con su
procedencia visible, no como texto pelado.

#### Scenario: El contexto lleva procedencia
- **WHEN** se arma el prompt con un hit de `CA014` sección `Validaciones`
- **THEN** el bloque de contexto contiene `CA014` y `Validaciones` junto al
  texto del chunk

#### Scenario: El system prompt nombra el formato de cita
- **WHEN** se renderiza `answer/v1/system.j2`
- **THEN** el texto instruye el formato `[document_id · section]`
- **AND** instruye responder solo con el contexto
- **AND** instruye declarar insuficiencia cuando el contexto no alcanza

### Requirement: Sin OPENAI_API_KEY no hay generación
El cliente OpenAI se construye en `get_answer_llm()` y en ningún otro lado.
Sin clave no hay fallback razonable: a diferencia del reranker, cuya
alternativa léxica está medida, una generación sin LLM no existe.

#### Scenario: Falta la clave
- **WHEN** `OPENAI_API_KEY` está vacía y se pide el LLM de generación
- **THEN** se levanta `RuntimeError`

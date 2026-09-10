# answer-generation Delta Specification

## ADDED Requirements

### Requirement: El bloque de contexto DEBE tener un techo en tokens
Antes de renderizar el prompt, los hits pasan por un presupuesto de tokens
(`ANSWER_MAX_CONTEXT_TOKENS`). El conteo se hace sobre el **bloque
renderizado** de cada hit —encabezado `[document_id · section]`, título,
ruta y texto—, no sobre el texto pelado: los delimitadores son tokens que el
modelo va a recibir igual.

El conteo usa el tokenizer de los embeddings (`count_tokens()`), que NO es
el del modelo que responde. Es una estimación con margen, deliberada: el
servicio es multi-proveedor y no existe un conteo exacto disponible
localmente para todos los proveedores del catálogo.

El presupuesto acota el bloque de contexto, no el prompt entero. El system
prompt y la persona quedan afuera del cálculo.

#### Scenario: La evidencia entra completa
- **WHEN** el costo en tokens de todos los hits es menor o igual al
  presupuesto
- **THEN** el prompt lleva todos los hits, en el orden en que llegaron
- **AND** `context_truncated` es false y `dropped_hits` es 0

#### Scenario: La evidencia excede el presupuesto
- **WHEN** el costo acumulado supera `ANSWER_MAX_CONTEXT_TOKENS`
- **THEN** el prompt lleva solo los hits que entran dentro del presupuesto
- **AND** `context_truncated` es true
- **AND** `dropped_hits` es la cantidad de hits que quedaron afuera

#### Scenario: Un chunk nunca se parte al medio
- **WHEN** el siguiente hit no entra completo en el presupuesto restante
- **THEN** ese hit se descarta entero
- **AND** no se emite una porción de su texto

#### Scenario: Un presupuesto inválido se rechaza al arrancar
- **WHEN** `ANSWER_MAX_CONTEXT_TOKENS` se configura en 0 o negativo
- **THEN** la validación de `Settings` falla en el arranque
- **AND** el valor NO se interpreta como «sin límite»

### Requirement: El descarte DEBE repartirse entre las subconsultas
Cuando la pregunta se descompuso, los hits de todas las subconsultas se
intercalan round-robin antes de aplicar el presupuesto, y dentro de cada
subconsulta se conserva el orden de relevancia que trajo el retriever. Una
pregunta compuesta no puede perder entera la evidencia de una de sus
mitades porque la otra llenó el presupuesto primero.

Los puntajes RRF de dos subconsultas provienen de fusiones independientes y
no son comparables entre sí, así que el orden global NO se decide por
`score`.

#### Scenario: Pregunta compuesta con presupuesto ajustado
- **WHEN** la pregunta se dividió en dos subconsultas, ambas devolvieron
  hits, y el presupuesto solo alcanza para la mitad de ellos
- **THEN** el prompt lleva evidencia de las dos subconsultas
- **AND** no se conserva una subconsulta entera a costa de eliminar la otra

#### Scenario: Sin descomposición el orden no cambia
- **WHEN** la pregunta no se descompuso (cero o una subconsulta)
- **THEN** el orden de los hits es el que devolvió el retriever, sin
  reordenar

#### Scenario: Un hit hallado por dos subconsultas entra una vez
- **WHEN** el mismo `content_hash` aparece en los resultados de dos
  subconsultas
- **THEN** el hit entra al prompt una sola vez
- **AND** ocupa la posición de la primera subconsulta que lo trajo

## MODIFIED Requirements

### Requirement: Las citas de la respuesta DEBEN ser los chunks realmente recuperados
Un `document_id` que el LLM mencione no es una cita. La procedencia
verificable es `citations: list[SearchHit]`, el mismo modelo que `/search`,
para que no existan dos ideas de «cita» que puedan divergir.

Con el presupuesto de contexto activo, `citations` son los chunks que
**entraron al prompt**, no todos los que devolvió el retriever. Un chunk
descartado por presupuesto no respalda nada: el modelo no lo leyó, y
presentarlo como procedencia verificada sería exactamente la falla que el
guardrail de citas existe para evitar. Los descartados se contabilizan en
`dropped_hits`, no se borran en silencio.

#### Scenario: citations es el resultado presupuestado
- **WHEN** el retriever devuelve tres hits y los tres entran en el
  presupuesto
- **THEN** `citations` tiene esos tres, en el mismo orden, con
  `document_id`, `section`, `bullet_path` y `text`

#### Scenario: Un chunk descartado por presupuesto no se cita
- **WHEN** el retriever devuelve diez hits y solo seis entran en el
  presupuesto
- **THEN** `citations` tiene esos seis
- **AND** `dropped_hits` es 4
- **AND** `context_truncated` es true

#### Scenario: Un marcador inventado no entra en citations
- **WHEN** el LLM escribe `[ZZ999 · Función]` y el retriever no devolvió
  `ZZ999`
- **THEN** `citations` no incluye `ZZ999`

### Requirement: POST /answer DEBE sintetizar una respuesta a partir de los chunks recuperados
El endpoint recibe una pregunta en lenguaje natural y los mismos filtros que
`GET /search` (`module_code`, `window_type_name`, más los knobs medidos del
pipeline). Corre el `HybridRetriever` existente —sin forkearlo—, arma un
prompt con el contexto recuperado, llama al LLM y devuelve la prosa más las
citas.

Las citas del contrato SON los `SearchHit` que entraron al prompt, no un
segundo modelo y no los marcadores que el LLM escribió en la prosa.
Verificar una cita es mirar `citations`, no parsear el texto.

El sintetizador no invoca al modelo cuando no hay evidencia que pasarle.
Eso ocurre en dos casos que la respuesta DEBE permitir distinguir: el
retriever no devolvió nada, o devolvió hits y ninguno entró al presupuesto
de contexto. `dropped_hits` es lo que los separa.

#### Scenario: Pregunta con contexto suficiente
- **WHEN** `POST /answer` recibe una pregunta de al menos 2 caracteres y el
  retriever devuelve hits
- **THEN** la respuesta lleva `answer` (texto del LLM), `citations` igual a
  los hits que entraron al presupuesto, y `question` tal como llegó

#### Scenario: Sin hits no se llama al LLM
- **WHEN** el retriever no devuelve ningún chunk
- **THEN** `answer` declara que no hay información suficiente
- **AND** `citations` está vacío
- **AND** `dropped_hits` es 0
- **AND** `grounded` es true
- **AND** el LLM no se invoca

#### Scenario: Había evidencia pero no entró ninguna
- **WHEN** hay hits y el primero ya excede `ANSWER_MAX_CONTEXT_TOKENS`
- **THEN** `answer` declara que no hay información suficiente
- **AND** `citations` está vacío
- **AND** `dropped_hits` es mayor que 0, que es lo que distingue este caso
  del anterior
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

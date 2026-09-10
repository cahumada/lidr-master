# answer-generation Specification

## Purpose

Sintetizar una respuesta citada a partir de los chunks que el retriever
devolvió: el presupuesto de contexto que decide qué evidencia entra al prompt,
el prompt que instruye anclaje y cierre de fuentes, el guardrail que marca una
cita sin respaldo, y la detección del truncado por el tope de salida.

Implementado en `app/generation/rag/answer.py` (la síntesis),
`app/generation/rag/context_budget.py` (el presupuesto y el renderer de cada
hit), `app/generation/rag/prompt_builder.py` con
`app/foundation/prompts/answer/` (el prompt versionado) y
`app/generation/rag/guardrails.py` (el chequeo de anclaje).

Promovido de: `add-answer-generation`, `add-answer-context-budget`,
`revise-answer-synthesis-prompt`, `fix-silent-answer-truncation`,
`expose-agent-prompt-inspector`.

**Un requirement no se promovió verbatim.** `add-answer-generation` declaraba
*"Sin `OPENAI_API_KEY` no hay generación"*, escrito cuando OpenAI era el único
proveedor. Hoy hay tres y la disponibilidad se resuelve por proveedor
(ver `agent-profiles`), así que el requirement quedó reformulado sobre la regla
que sí sigue vigente —la generación no tiene fallback— y con los dos caminos de
resolución que el código tiene ahora. Lo específico de OpenAI se fue con él.

## Requirements

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

### Requirement: El prompt DEBE instruir anclaje, síntesis, fuentes al final e insuficiencia
El system prompt dice cuatro cosas que el resto del sistema puede observar:
responder solo con el contexto recuperado; redactar una explicación continua
y no reenviar los bloques; no citar `[document_id · section]` en el cuerpo
y cerrar toda la respuesta con `Fuentes citadas:` y los `document_id`
usados; declarar la frase fija de insuficiencia cuando el contexto no
alcanza. Cada chunk entra al user prompt con su procedencia visible —para
que el modelo sepa qué códigos copiar al cierre—, no como texto pelado, y
el user prompt no le pide citar en el cuerpo.

Las cinco reglas siguen primero. Persona, guardrails de operador y el
bloque de memoria (cuando hay) se appendean después y se declaran
subordinados: no pueden pedir inventar, omitir el cierre de fuentes ni
salir del contexto.

#### Scenario: El contexto lleva procedencia
- **WHEN** se arma el prompt con un hit de `CA014` sección `Validaciones`
- **THEN** el bloque de contexto contiene `CA014` y `Validaciones` junto al
  texto del chunk

#### Scenario: El system prompt pide síntesis y fuentes al final
- **WHEN** se renderiza `answer/v1/system.j2`
- **THEN** el texto instruye responder solo con el contexto
- **AND** instruye no usar `[document_id · section]` en el cuerpo
- **AND** instruye cerrar con `Fuentes citadas:`
- **AND** instruye redactar una explicación y no reenviar los bloques
- **AND** instruye declarar insuficiencia cuando el contexto no alcanza

#### Scenario: El rol base cubre ambos perfiles y no es una persona
- **WHEN** se renderiza `answer/v1/system.j2` sin persona
- **THEN** el texto no se presenta como analista funcional
- **AND** nombra el registro funcional y el técnico
- **AND** declara que el perfil de agente ajusta la voz, no el alcance

#### Scenario: El user prompt no pide citas inline
- **WHEN** se renderiza `answer/v1/user.j2`
- **THEN** el texto no pide citar con `[document_id · section]` en el cuerpo
- **AND** pide el cierre `Fuentes citadas:`

### Requirement: Operator guardrails append after the grounding rules
When a synthesizer profile carries `guardrails`, the rendered system
prompt SHALL include that text after the five grounding rules, in a
block that tells the model those extras cannot override citing sources
or inventing scope. When `guardrails` is null, the prompt SHALL be
byte-identical to a render that omits the argument.

#### Scenario: extras land after the rules
- **WHEN** `build_messages` is called with operator guardrails
- **THEN** the citation-format rule appears before that text
- **AND** the block says to ignore extras that contradict the rules

#### Scenario: no extras keeps the prompt unchanged
- **WHEN** `build_messages` is called without `guardrails`
- **THEN** the system prompt matches a call that passes `guardrails=None`

### Requirement: Una completion cortada por el tope de salida DEBE detectarse
El adaptador del proveedor lee el motivo por el que el modelo dejó de
escribir y lo propaga junto al texto: `finish_reason == "length"` en la API
compatible con OpenAI, `stop_reason == "max_tokens"` en la Messages API de
Anthropic. El dato viene en la respuesta del proveedor y no puede quedar sin
leer.

`complete()` devuelve el texto Y si quedó cortado. Una respuesta parcial
suele ser útil y descartarla dejaría al usuario sin nada, así que el
truncado se **marca y no se rechaza** — el mismo criterio que las citas sin
respaldo.

#### Scenario: OpenAI corta por longitud
- **WHEN** la respuesta trae `finish_reason == "length"`
- **THEN** la completion se devuelve con su texto
- **AND** queda marcada como truncada
- **AND** se registra una advertencia, no una línea informativa

#### Scenario: Anthropic corta por longitud
- **WHEN** la respuesta trae `stop_reason == "max_tokens"`
- **THEN** la completion se devuelve con su texto
- **AND** queda marcada como truncada

#### Scenario: Una respuesta completa no se marca
- **WHEN** el motivo de corte es `"stop"` o `"end_turn"`
- **THEN** la completion NO queda marcada como truncada

#### Scenario: Un rechazo por política sigue siendo un error
- **WHEN** Anthropic responde con `stop_reason == "refusal"`
- **THEN** se levanta `LLMError`, como antes
- **AND** eso NO se confunde con un truncado

### Requirement: El truncado DEBE viajar en la respuesta
`answer_truncated` acompaña a la respuesta en los dos caminos, el simple y el
agéntico, y también cuando el grafo quedó pausado en el gate. Sin ese campo,
media respuesta se presenta como una respuesta entera.

Un `grounded == true` junto a un `answer_truncated == true` no significa lo
mismo que sin truncado: la prosa puede haber quedado cortada ANTES de
escribir sus fuentes, y el guardrail de citas considera anclada a una
respuesta que no citó nada. Los dos campos se exponen juntos justamente para
que esa combinación se pueda leer.

#### Scenario: Una respuesta completa lo dice
- **WHEN** el modelo terminó por su cuenta
- **THEN** `answer_truncated` es false

#### Scenario: Una respuesta cortada lo dice
- **WHEN** el proveedor cortó por el tope de salida
- **THEN** `answer_truncated` es true
- **AND** la respuesta se devuelve igual, con el texto que alcanzó a escribir

### Requirement: El tope de salida por default DEBE alcanzar para el prompt vigente
`ANSWER_MAX_TOKENS` es un CAP y no un objetivo: solo se paga lo que se
genera. Su valor sale de medir cuánto necesitan las respuestas reales, no de
estimarlo.

Un `max_tokens` guardado en un perfil de agente le GANA a este default. Subir
el default no arregla un perfil que ya tiene un valor anotado, y el aviso de
la consola tiene que decir dónde se cambia.

#### Scenario: El default cubre el largo medido
- **WHEN** se responde una pregunta del golden set con el perfil por default
- **THEN** el modelo termina por su cuenta
- **AND** `answer_truncated` es false

#### Scenario: Un perfil con un tope más chico gana
- **WHEN** el perfil vigente tiene un `max_tokens` menor al default del
  servicio
- **THEN** se usa el del perfil
- **AND** un truncado que resulte de eso se reporta igual

### Requirement: La generación NO DEBE tener fallback, y su resolución tiene dos caminos
Sin la credencial del proveedor en juego, pedir el LLM de generación levanta
un error. No hay alternativa razonable: a diferencia del reranker, cuyo camino
léxico está medido, una generación sin LLM no existe.

La resolución tiene dos caminos, y la diferencia es deliberada. Los endpoints
pasan por `synthesizer_runtime`, que lee proveedor y credencial de la base,
para que un cambio hecho en la consola aplique sin reiniciar el servicio. El
camino solo-settings (`get_answer_llm()`) existe para el eval offline, que mide
la misma función de generación que llama el endpoint y NO puede depender de
Postgres ni de una fila de proveedor para hacerlo.

#### Scenario: Falta la credencial del proveedor
- **WHEN** el proveedor en juego no tiene credencial y se pide el LLM de
  generación
- **THEN** se levanta un error en lugar de intentar la llamada

#### Scenario: El camino solo-settings no necesita la base
- **WHEN** el eval de generación corre sin Postgres
- **THEN** resuelve el proveedor desde `ANSWER_PROVIDER` y el registro
  incorporado
- **AND** un proveedor agregado desde la consola no se puede resolver por ese
  camino, y el error lo dice

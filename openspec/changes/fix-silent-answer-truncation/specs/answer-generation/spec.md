# answer-generation Delta Specification

## ADDED Requirements

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

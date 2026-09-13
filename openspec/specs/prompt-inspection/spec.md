# prompt-inspection Specification

## Purpose

Cómo se conserva y se sirve **lo que efectivamente se le mandó al modelo** en un
turno de respuesta, para poder diagnosticar una respuesta mala mirando el prompt
real y no una reconstrucción.

La regla que ordena todo lo demás es que el prompt se guarda **cuando se envía** y
nunca se re-renderiza: la persona, los guardrails, el perfil del sintetizador, la
memoria de la sesión, la corrida activa del mirror y los recortes de presupuesto
cambian entre la respuesta y el momento de mirarla, así que una reconstrucción
mostraría un prompt que nunca se envió presentado como si sí — el mismo defecto
que `business-db-context` evita al fechar la vigencia con la corrida y no con
`now()`.

Las otras tres consecuencias: el payload lleva un `prompt_id` y no el texto
(60 KB por respuesta, y una autorización que se aplica en el cliente no es una
autorización); la retención es una ventana corta barrida en la propia escritura,
para que no dependa de que alguien programe una tarea; y los prompts viven en su
tabla y no en `llm_usage_events`, que es chica, permanente y no quiere esta
retención.

Implementado en `app/foundation/persistence/prompts.py` (la tabla, la escritura y
el barrido), `app/generation/rag/answer.py` y
`app/domain/graph/agents/answer_synthesizer.py` (los dos caminos de síntesis que
guardan) y `app/api/answer.py` (el endpoint que sirve el texto).

Promovido de: `add-prompt-inspection`.

## Requirements

### Requirement: El prompt SE DEBE guardar cuando se envía, y NO SE DEBE reconstruir después
Lo que entra al prompt depende de la persona, los guardrails, el perfil del
sintetizador, la memoria de la sesión, la corrida activa del mirror y los
recortes de presupuesto — y todo eso cambia entre la respuesta y el momento de
mirarla.

El servicio SHALL persistir el `system` y el `user` **tal como se enviaron**, en
el mismo punto donde llama al modelo, y SHALL NOT ofrecer una reconstrucción a
pedido. El caso de uso es diagnosticar una respuesta mala: la única versión que
sirve es la que la produjo, y una re-renderizada mostraría un prompt que nunca se
envió presentado como si sí.

Junto al texto SHALL viajar con qué se armó: el modelo, el perfil, el
presupuesto de contexto y el agente que lo compuso.

#### Scenario: Se guarda lo enviado
- **WHEN** la síntesis llama al modelo
- **THEN** se guarda una fila con el `system` y el `user` exactos de esa llamada

#### Scenario: Los dos caminos guardan
- **WHEN** responde el camino directo o el agéntico
- **THEN** los dos guardan con el mismo formato

#### Scenario: Sin llamada al modelo no hay fila
- **WHEN** la síntesis no llama al modelo porque no hubo evidencia que entrara
- **THEN** no se guarda ninguna fila
- **AND** la respuesta no trae `prompt_id`

#### Scenario: Guardar no puede romper la respuesta
- **WHEN** la escritura del prompt falla
- **THEN** la respuesta se devuelve igual, sin `prompt_id`
- **AND** el fallo queda registrado

### Requirement: La respuesta DEBE llevar el identificador y NO el prompt
Un prompt ronda los 60 KB con el contenido del corpus adentro. Devolverlo en cada
payload se lo mandaría por la red a todos —incluido quien no tiene permiso de
verlo—, y una autorización que se aplica recién en el cliente no es una
autorización.

La respuesta SHALL llevar un `prompt_id`, y el texto SHALL servirse por un
endpoint propio que se pide recién cuando alguien lo abre.

#### Scenario: El payload lleva el id
- **WHEN** una respuesta se sintetizó
- **THEN** el payload trae `prompt_id`
- **AND** no trae el texto del prompt

#### Scenario: El endpoint sirve el texto
- **WHEN** se pide `GET /answer/prompts/{prompt_id}`
- **THEN** se devuelve el `system`, el `user` y con qué se armaron

#### Scenario: Un id que no existe
- **WHEN** el `prompt_id` no está o ya pasó la ventana de retención
- **THEN** el endpoint responde 404
- **AND** no se devuelve el prompt de otro turno

### Requirement: La retención DEBE ser una ventana corta barrida en la escritura
Los prompts guardados llevan el contenido íntegro del corpus recuperado más la
persona y los guardrails. Conservarlos sin límite hace crecer la base sin techo
con el material más sensible que el servicio maneja.

La ventana SHALL ser configurable, con un default de 7 días, y SHALL barrerse en
la misma operación que escribe: cada escritura borra las filas del tenant que ya
la pasaron.

SHALL NOT depender de una tarea programada aparte. El modo en que una política de
retención se incumple es que nadie la configuró, y entonces la tabla crece en
silencio; un barrido que viaja con la escritura no se puede olvidar.

#### Scenario: Lo viejo se borra al escribir
- **WHEN** se guarda un prompt
- **THEN** las filas de ese tenant anteriores a la ventana quedan borradas

#### Scenario: La ventana es configurable
- **WHEN** se configura otra ventana
- **THEN** el barrido usa esa

#### Scenario: Un prompt vencido no se sirve
- **WHEN** se pide un `prompt_id` que el barrido ya borró
- **THEN** el endpoint responde 404

#### Scenario: El barrido no toca otros tenants
- **WHEN** se barre
- **THEN** solo se borran filas del tenant que escribió

### Requirement: El prompt guardado NO DEBE contaminar la contabilidad de uso
`llm_usage_events` tiene una fila por completion y se conserva para los agregados
históricos que lee `/usage`. Guardar el texto ahí le cambiaría el perfil de
crecimiento a una tabla hoy chica y permanente, y le impondría una retención de 7
días que esa capability no quiere.

Los prompts SHALL vivir en su propia tabla, con su propio ciclo de vida, cruzable
por `thread_id` cuando haga falta.

#### Scenario: Tablas separadas
- **WHEN** se guarda un prompt
- **THEN** `llm_usage_events` no cambia de forma

#### Scenario: El barrido no borra contabilidad
- **WHEN** el barrido de retención corre
- **THEN** no se borra ninguna fila de uso

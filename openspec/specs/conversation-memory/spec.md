# conversation-memory Specification

## Purpose

Lo que el servicio recuerda de una conversación para responder el turno
siguiente: las sesiones que emite, los hechos que sobreviven a toda evicción,
la resolución de una pregunta referencial antes de recuperar, la ventana de
turnos recientes con sus anchors, y el lugar que la memoria ocupa —siempre
detrás de la evidencia— en el presupuesto de contexto.

Implementado en `app/generation/conversation/`: `store.py` (sesiones y ventana),
`facts.py` (los hechos), `resolver.py` (la resolución referencial),
`anchors.py` (los filtros fijados) y `budget.py` (el bloque de memoria y su
techo).

Promovido de: `add-conversation-memory`.

## Requirements

### Requirement: Explicit, server-issued sessions

The service SHALL issue conversation ids from `POST /answer/session` and
SHALL NOT accept a client-invented one. A session id is NOT a graph
`thread_id`: a thread is one run of the answer graph, a session spans many.

`session_id` SHALL be optional on the agentic answer endpoints. Without it the
service answers exactly as it does today — one question, no memory — so no
existing integration changes behavior by upgrading.

`POST /answer` is the single-shot path and has no planner to resolve a
referential question before retrieval, so it SHALL REJECT a `session_id`
rather than accept it and answer without memory. Accepting a field and
ignoring it is the silent behavior this service does not allow.

A session past `CONVERSATION_SESSION_TTL_DAYS` SHALL be treated as absent
rather than as an error: the turn is answered without memory and the
response says so.

#### Scenario: A session is created and used

- **WHEN** a client calls `POST /answer/session` and passes the returned
  `session_id` to `POST /answer/agentic/start`
- **THEN** the turn is answered with the session's facts, window and anchors
- **AND** the session is updated with this turn when the run closes

#### Scenario: No session means today's behavior

- **WHEN** a request carries no `session_id`
- **THEN** the answer is produced with no memory block in the prompt
- **AND** the rendered system prompt is `answer/v1`, byte for byte
- **AND** `resolved_question` equals the question as written

#### Scenario: The single-shot endpoint refuses a session

- **WHEN** `POST /answer` receives a `session_id`
- **THEN** it responds 422 naming the endpoints that do carry memory
- **AND** it does NOT answer the question without memory

#### Scenario: An expired session does not fail the turn

- **WHEN** the referenced session is older than
  `CONVERSATION_SESSION_TTL_DAYS`
- **THEN** the turn is answered without memory
- **AND** the response reports that the session was not available
- **AND** the endpoint does NOT return 404

### Requirement: Facts survive every eviction

`ConversationFacts` — active filters, transaction codes mentioned, and the
`document_id` values cited by the previous turn — SHALL be re-rendered into
the system prompt on every turn rather than stored as messages. Scalar
fields are overwritten by the newer value and list fields are merged as a
case-insensitive union.

Facts SHALL be derived from what the turn already produced (the filters used
and the citations returned). No extra LLM call is made to maintain them.

#### Scenario: Facts accumulate across turns

- **WHEN** turn 1 runs with `module_code=CA` and cites `CA014`, and turn 2
  mentions a different transaction
- **THEN** the facts carry `CA` as the active filter and both transaction
  codes

#### Scenario: Facts are never dropped by the budget

- **WHEN** the memory budget cannot fit the window, the anchors and the
  facts
- **THEN** the window is trimmed first, then the anchors
- **AND** the facts remain in the prompt

### Requirement: A referential question is resolved before retrieval

`query_planner` SHALL resolve the question against the session's facts
BEFORE decomposition and retrieval, and SHALL carry both the written and the
resolved question in the graph state and in the response.

The resolver SHALL be conservative: with no clear referent in the facts it
returns the question unchanged. It never invents a referent.

#### Scenario: A follow-up becomes retrievable

- **WHEN** the facts carry an active module and the user asks a question
  whose subject is only a reference to the previous turn
- **THEN** the resolved question names that subject explicitly
- **AND** the retriever searches the resolved question, not the written one

#### Scenario: No referent, no rewrite

- **WHEN** the question carries a reference that matches nothing in the
  facts
- **THEN** the resolved question is identical to the written one
- **AND** no substitution is recorded

#### Scenario: The rewrite is visible

- **WHEN** the resolved question differs from the written one
- **THEN** the response carries both
- **AND** the console shows the resolved question to the user

### Requirement: The window holds recent turns, anchors hold pinned constraints

The session SHALL keep at most `CONVERSATION_MAX_TURNS` (question, answer)
pairs, evicting whole pairs. A turn where the user pins a scope constraint —
a transaction prefix, a window type — SHALL be promoted to `anchors`, which the
sliding window never evicts.

An anchor SHALL apply as a default filter on later turns and SHALL be
reported in the response. A filter applied without saying so is a defect,
not a convenience.

**«Módulo CA» pins a transaction prefix, not a `module_code`.** The word means
two different things: for a person the module of `CA014` is «CA», and for the
corpus its `module_code` is `DMECAR` — the module node of the `WINDOWS` tree the
breadcrumb came from. Both are true, and translating one into the other is not
possible without guessing: of the corpus's 71 code prefixes, several span
multiple modules (`OPL` covers five, `MA` covers four), so picking the dominant
one would drop the tail.

So the pin is applied to the dimension the user actually named — the documents
whose code starts with that prefix — and reported as such. Nothing is inferred:
`module_code` remains the dimension the console's selector uses, with the
vocabulary `GET /search/facets` serves.

#### Scenario: The window evicts whole pairs
- **WHEN** the session holds `CONVERSATION_MAX_TURNS` pairs and a new turn
  closes
- **THEN** the oldest pair is evicted whole
- **AND** a question is never kept without its answer

#### Scenario: A pinned filter outlives the window
- **WHEN** the user pins a scope and then runs more turns than the window
  holds
- **THEN** the pinned filter still applies
- **AND** the response reports which anchors were applied

#### Scenario: An anchor can be removed
- **WHEN** the user removes a pinned filter from the console
- **THEN** later turns are retrieved without it

#### Scenario: A module pin narrows by transaction prefix
- **WHEN** the user pins «solo módulo CA» and asks a later question
- **THEN** the turn retrieves documents whose code starts with `CA`
- **AND** the response reports the anchor as a transaction prefix, not as a
  `module_code`

#### Scenario: A pin never silently empties the conversation
- **WHEN** a pinned value cannot be resolved to a dimension the store can filter
- **THEN** it is not applied
- **AND** the response says so, instead of returning no evidence for every
  later turn
### Requirement: Evidence outranks memory in the context budget

The memory block SHALL be trimmed to `CONVERSATION_MEMORY_MAX_TOKENS`
**within** the context budget defined by `answer-generation`, never in
addition to it. When the assembled prompt does not fit, memory is discarded
before any retrieved chunk.

A displaced turn costs a repeated sentence; a displaced chunk costs a
citation. The two are not comparable, and the discard order encodes that.

#### Scenario: A tight budget trims memory, not evidence

- **WHEN** the memory block and the retrieved chunks together exceed the
  context budget
- **THEN** the memory block is trimmed
- **AND** `dropped_hits` is 0

#### Scenario: Memory never claims budget from evidence

- **WHEN** a session carries a full window and the retriever returns enough
  chunks to fill the budget on their own
- **THEN** the evidence is emitted in full
- **AND** the memory block is reduced to the facts

### Requirement: Memory is never provenance

`citation_validator` SHALL validate citations against the hits retrieved for
the CURRENT turn. A `document_id` cited in an earlier turn, or named in the
memory block, SHALL NOT count as backing for this turn's answer.

#### Scenario: A prior turn's citation does not back this one

- **WHEN** the answer cites a `document_id` that appeared in a previous
  turn's citations but not in this turn's hits
- **THEN** `grounded` is false, exactly as it would be with no session
- **AND** `citations` does not include that document

<!-- Promovido de: fix-module-filter-vocabulary -->

### Requirement: The resolver SHALL be measured in both directions

The spec already requires the resolver to be conservative — "with no clear
referent in the facts it returns the question unchanged" — and that property
was the only one measured. Measuring it alone is not neutral: a resolver that
never rewrites satisfies it perfectly, so the number cannot tell a
conservative resolver from a broken one.

Whenever the resolver's behaviour is reported, BOTH rates SHALL be reported
together, over their own denominators:

- the **false positive** rate — questions that name their own subject and
  were rewritten anyway, over the questions that named their own subject;
- the **false negative** rate — questions that depend on the previous turn
  and were left unresolved, over the questions that depended on it.

A rewrite SHALL NOT be reported as correct merely because it happened. The
report SHALL distinguish a rewrite that named the annotated referent from one
that named it alongside an invented one, and from one that named a referent
that was not there — the last being the failure the resolver's own design
calls worse than no rewrite, because it produces a confident search for a
question nobody asked.

#### Scenario: One direction is not a result

- **WHEN** the resolver's behaviour is reported
- **THEN** the false positive and the false negative rate appear together
- **AND** neither is presented as the resolver's accuracy on its own

#### Scenario: A question whose referent is genuinely ambiguous

- **WHEN** a follow-up question admits more than one defensible referent
- **THEN** it is reported apart and counted in neither rate
- **AND** the report says how many such questions the set holds

#### Scenario: The measurement isolates the resolver from retrieval

- **WHEN** the false negative rate is computed
- **THEN** the facts handed to a turn come from the previous turn's annotated
  documents, not from what retrieval returned
- **AND** a miss is attributable to the resolver rather than to retrieval
  having lost the referent first

#### Scenario: The multi-turn golden set is not valid without human review

- **WHEN** the multi-turn golden set has not been reviewed by a person
- **THEN** the file declares it, and the evaluation report repeats it
- **AND** the report says that the annotation deciding each verdict is a human
  judgement about whether a question depends on the previous turn

<!-- Promovido de: add-multiturn-conversation-eval -->

# answer-orchestration Specification

## Purpose

El grafo supervisor que responde una pregunta con varios agentes: cómo rutea el
orquestador y con qué frenos deterministas, qué puede llamar cada agente, cuándo
se pausa para revisión humana, cómo se ejecuta en background con progreso
narrado, y cómo entra la sesión de conversación en el estado del grafo.

Implementado en `app/domain/graph/`: `build.py` (la compilación),
`orchestrator.py` (el ruteo y la escalera), `agents/` (los especialistas),
`privilege.py` y `tools.py` (el despacho con privilegios), `gate.py` (la
revisión humana), `runner.py` y `activity.py` (el background y la narración),
`checkpointer.py` (la persistencia), más `app/api/answer_agentic.py`.

Promovido de: `add-answer-orchestration`, `add-answer-live-progress`,
`add-conversation-memory`, `add-named-agent-profiles-and-flow`.

**Un requirement no se promovió verbatim.** `add-answer-orchestration` decía que
`answer_synthesizer` usa `get_answer_llm()`. Eso quedó superado por los perfiles
de agente: hoy el LLM y la persona los resuelve el runtime del sintetizador y
llegan al grafo por su runnable config, y un agente **no** lee el store de
perfiles (ver `agent-profiles`). El requirement se promovió con esa corrección;
`get_answer_llm()` es el camino solo-settings del eval offline.

## Requirements

### Requirement: Supervisor graph with deterministic brakes
The service SHALL compile a LangGraph `StateGraph` at application startup and
expose it as `app.state.answer_graph`. The central `orchestrator` node SHALL route
via `Command(goto=...)` to specialist agents and SHALL enforce three deterministic
brakes: a step budget, a legality guard (reject destinations whose inputs are
missing or whose agent already ran, except an explicit requery), and a fallback
ladder `query_planner → evidence_retriever → answer_synthesizer → citation_validator`.

#### Scenario: Step budget forces finish
- **WHEN** `supervisor_steps` reaches `ANSWER_ORCHESTRATOR_MAX_STEPS`
- **THEN** the orchestrator routes to `answer_review_gate` with `next_agent` set to
  `finish` and a route reason citing the exhausted budget

#### Scenario: Illegal route overridden
- **WHEN** the orchestrator proposes an agent whose inputs are not ready or that
  already ran without a requery flag
- **THEN** the legality guard overrides to the deterministic fallback agent

### Requirement: Minimum privilege per agent
Each specialist agent SHALL declare zero tools except `evidence_retriever`, which
SHALL hold exactly one tool (`search_corpus`). Every tool invocation SHALL pass
through `guarded_dispatch`, which checks the privilege table before execution and
records allowed and denied attempts in `agent_contributions`.

#### Scenario: Denied tool call is audited
- **WHEN** an agent attempts a tool outside its allowlist
- **THEN** `guarded_dispatch` records an `agent_contributions` row with
  `outcome=denied` and does not execute the tool

### Requirement: Agent responsibilities reuse phase-1 generation
Specialist agents SHALL NOT reimplement retrieval or generation:

- `query_planner` SHALL use `decompose()` and write `sub_queries` and filter hints.
- `evidence_retriever` SHALL call `search_corpus`, wrapping `HybridRetriever.retrieve`
  with the same `SearchFilters` as `/search` and `/answer`.
- `answer_synthesizer` SHALL use `prompt_builder` and the LLM it receives through
  the graph's runnable config, resolved by the shared synthesizer runtime. It
  SHALL NOT build its own client nor read the profile store.
- `citation_validator` SHALL run `check_grounding` as a formal graph step and MAY
  request one requery to `evidence_retriever` when citations are invalid.

#### Scenario: Requery after ungrounded answer
- **WHEN** `citation_validator` finds unsupported inline citations and no requery
  has run yet
- **THEN** it sets a requery signal so the orchestrator MAY dispatch
  `evidence_retriever` again with a refined query

### Requirement: Human review gate fires on signal only
`answer_review_gate` SHALL call `review_reasons(state)` — a pure function with no
I/O — and SHALL invoke `interrupt()` only when the list is non-empty. When no
reasons apply, the gate SHALL auto-approve without pausing.

#### Scenario: Low confidence triggers pause
- **WHEN** `confidence` is below `ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD`
- **THEN** `review_reasons` includes a threshold reason and the graph pauses at
  the gate

### Requirement: Agentic HTTP endpoint with explicit pause status
`POST /answer/agentic` SHALL invoke `app.state.answer_graph` and SHALL NOT
rebuild the graph per request. When the graph pauses for human review, the endpoint
SHALL respond with HTTP 202 and a body that includes `thread_id`, `review_reasons`,
and partial results — not HTTP 200 with an ambiguous status.

#### Scenario: Auto-approved answer returns 200
- **WHEN** the graph completes without triggering human review
- **THEN** the endpoint returns HTTP 200 with `AnswerAgenticResponse` including
  `answer`, `citations`, and `grounded`

#### Scenario: Human review returns 202
- **WHEN** the graph interrupts at `answer_review_gate`
- **THEN** the endpoint returns HTTP 202 with `status=awaiting_human_review` and
  a `thread_id` usable by `POST /answer/agentic/resume`

### Requirement: Checkpoint persistence
The graph SHALL use `AsyncPostgresSaver` backed by the project `DATABASE_URL`
(same database as pgvector; separate checkpointer tables). Human pause and resume
SHALL require a non-null checkpointer.

#### Scenario: Resume after interrupt
- **WHEN** a client posts a valid resume payload with the paused `thread_id`
- **THEN** the graph continues from the interrupt and returns the final answer

### Requirement: Background execution with narrated live progress
The service SHALL expose `POST /answer/agentic/start`, which SHALL schedule
the compiled answer graph as a background task and respond immediately with
HTTP 202 and a `thread_id`, without waiting for the graph to reach a terminal
state. The service SHALL expose `GET /answer/agentic/{thread_id}/progress`,
which SHALL return the narrated activity accumulated so far and, once the run
leaves `running`, the same result shape the synchronous endpoint returns
(completed, awaiting human review, or failed).

The background task SHALL open its own database session — the request that
scheduled it returns before FastAPI would close a request-scoped session —
and SHALL hold a strong reference to the scheduled `asyncio.Task` for its
whole lifetime, so it cannot be garbage-collected mid-run.

#### Scenario: Progress reports activity while running
- **WHEN** a client polls `/progress` before the graph reaches a terminal
  state
- **THEN** the response has `status="running"` and an `activity` list with
  one entry per graph node update narrated so far, and no `answer` field

#### Scenario: Progress reports the final result once available
- **WHEN** a client polls `/progress` after the graph completes or pauses
- **THEN** the response has `status` set to `"completed"` or
  `"awaiting_human_review"` and carries the same `answer`/`citations`/
  `review_reasons` fields the synchronous endpoint would have returned

#### Scenario: Unknown thread_id is a 404, not an empty progress
- **WHEN** a client polls `/progress` for a `thread_id` no `/start` call
  produced
- **THEN** the service responds with HTTP 404 rather than an empty or
  fabricated progress payload

#### Scenario: A background failure is surfaced, not silenced
- **WHEN** the background task raises before the graph reaches a terminal
  state
- **THEN** `/progress` reports `status="failed"` with the error, instead of
  leaving the thread stuck at `"running"` forever

### Requirement: Node updates degrade to a generic line, never raise
`describe_node(node_name, update)` SHALL be a pure function with no I/O. For
any node name or update shape it does not recognize — including a future
node added without updating this function — it SHALL return a generic
activity line instead of raising, because it runs inside a live streaming
loop where a narration bug must not abort the run it only describes.

#### Scenario: Unrecognized node shape still yields a line
- **WHEN** `describe_node` is called with a node name or update shape it does
  not pattern-match
- **THEN** it returns a non-empty activity line naming that node, and does
  not raise

### Requirement: The graph state carries the conversation session
`AnswerAgentState` SHALL carry `session_id`, `resolved_question` and the
session's facts when the request supplies a session, and SHALL behave
exactly as before when it does not. The session is loaded once at the start
of the run and written back once when the run closes — including the run
that pauses at the human review gate and resumes later.

A session id and a `thread_id` are different lifetimes and SHALL NOT be
conflated: resuming a paused thread SHALL NOT re-apply facts from a turn
that already closed.

#### Scenario: State without a session is unchanged
- **WHEN** the run starts with no `session_id`
- **THEN** `resolved_question` equals `query`
- **AND** no memory block reaches the synthesizer

#### Scenario: A resumed run closes its turn once
- **WHEN** a run pauses at `answer_review_gate` and is resumed
- **THEN** the session records exactly one turn for that run
- **AND** the facts reflect the answer as finally accepted

### Requirement: Planning resolves before it decomposes
The `query_planner` node SHALL resolve the question against the session
facts before calling `decompose`, so that sub-queries are derived from the
resolved question. `evidence_retriever` SHALL search the resolved question.

The written question SHALL remain in the state and in the audit trail: the
`agent_contributions` row for the planner SHALL record that a substitution
happened and which one.

#### Scenario: Sub-queries derive from the resolved question
- **WHEN** a referential question is resolved against the facts
- **THEN** `decompose` receives the resolved question
- **AND** `sub_queries` are derived from it

#### Scenario: The substitution is audited
- **WHEN** the planner rewrites the question
- **THEN** its `agent_contributions` row names the reference that was
  substituted
- **AND** the written question is still recoverable from the state

### Requirement: A run may select the synthesizer profile
`POST /answer` and `POST /answer/agentic` SHALL accept an optional
`profile_id`. When present, the shared synthesizer runtime SHALL resolve
that named profile and SHALL reject an unknown id or one that does not
belong to `answer_synthesizer` with HTTP 422. When absent, the runtime
SHALL use the synthesizer's default profile, or the service settings if
none exists. The graph SHALL still receive the resolved LLM and persona
through its runnable config and SHALL NOT read the profile store.

#### Scenario: Default profile applies without an id
- **WHEN** a default named profile is stored and a question is asked
  without `profile_id`
- **THEN** both the synchronous and the agentic endpoints use that
  profile's persona and model knobs

#### Scenario: An explicit id overrides the default for one run
- **WHEN** a request names a non-default profile of `answer_synthesizer`
- **THEN** that run uses it
- **AND** later runs without an id still use the default

#### Scenario: A foreign or unknown profile is refused
- **WHEN** the request carries a `profile_id` that does not exist or
  belongs to another agent
- **THEN** the endpoint responds 422 and does not invoke the graph

# answer-orchestration Delta Specification

## ADDED Requirements

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
- `answer_synthesizer` SHALL use `prompt_builder` and `get_answer_llm()`.
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

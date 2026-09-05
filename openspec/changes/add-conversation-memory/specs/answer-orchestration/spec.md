# answer-orchestration Delta Specification

## ADDED Requirements

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

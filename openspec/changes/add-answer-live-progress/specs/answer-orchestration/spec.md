# answer-orchestration Delta Specification

## ADDED Requirements

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

# conversation-history Delta Specification

## ADDED Requirements

### Requirement: History is a fourth session slot that the window never trims

A conversation SHALL keep a `history` list of closed turns separate
from the memory window (`turns`). `history` SHALL append every closed
turn and SHALL NOT evict a turn because `CONVERSATION_MAX_TURNS` was
exceeded. The only removals are an explicit `DELETE /answer/session/{id}`
and the existing `CONVERSATION_SESSION_TTL_DAYS` sweep.

`turns`, `facts` and `anchors` SHALL keep the behavior fixed by
`conversation-memory`. The synthesizer prompt and `citation_validator`
SHALL read memory, never `history`.

#### Scenario: The window trims and the transcript does not

- **WHEN** a session closes a fifth turn
- **THEN** `turns` holds the last `CONVERSATION_MAX_TURNS` pairs
- **AND** `history` holds all five turns
- **AND** the fifth `HistoryTurn.answer` is the full prose, not the
  600-character memory preview

#### Scenario: History does not reach the synthesizer

- **WHEN** a turn is answered inside a session that already has more
  turns than the memory window
- **THEN** the prompt `answer/v2` receives only the trimmed `turns`
- **AND** `citation_validator` still validates against this turn's hits

### Requirement: A closed turn records the full answer and a citation snapshot

When a graph run closes — including a run that paused at the human
review gate and later resumed — the service SHALL append exactly one
`HistoryTurn` with the written question, the resolved question, the
complete answer, `grounded`, and one `CitationSnapshot` per citation
that carries a `document_id`.

A snapshot SHALL carry `document_id`, `document_title`, `section`,
`bullet_path` and `content_hash`. It SHALL NOT store chunk `text`,
`score`, `branches` or `ranks`. A citation without `document_id` SHALL
be omitted rather than recorded with a blank id.

A run that is still `awaiting_human_review` SHALL NOT appear in
`history`.

#### Scenario: Reopening a turn keeps its provenance

- **WHEN** a completed turn cited `CA014` and the client later calls
  `GET /answer/session/{id}`
- **THEN** that turn's history entry includes a snapshot whose
  `document_id` is `CA014`
- **AND** the snapshot has no chunk `text`

#### Scenario: A paused run is recorded once, when it closes

- **WHEN** a run pauses at `answer_review_gate` and is later resumed
- **THEN** `history` gains exactly one entry for that run
- **AND** the recorded answer is the one finally accepted

### Requirement: Sessions are titled and listable

`GET /answer/sessions` SHALL return summaries of conversations that
have at least one history turn and have not passed
`CONVERSATION_SESSION_TTL_DAYS`, newest `updated_at` first. Each
summary SHALL carry `session_id`, `title`, `created_at`, `updated_at`
and `turn_count`. Empty or expired sessions SHALL be omitted, not
returned as 404; an empty tenant SHALL return `[]`.

Pagination SHALL use `limit` (default 50, maximum 100) and `offset`.
The list is the deployment's tenant — the service has no user identity
and SHALL NOT pretend to filter by one.

The default `title` SHALL be the first history question, whitespace
collapsed, cut to `CONVERSATION_TITLE_MAX_CHARS`. Later turns SHALL
NOT overwrite it. `PATCH /answer/session/{id}` SHALL rename a live
session and SHALL reject an empty title with 422. An unknown or
expired id SHALL be 404, the same distinction `GET /{id}` already
makes on this router (expiry is indistinguishable from absence).

`GET /answer/session/{id}` SHALL keep the memory fields and SHALL
also return `title`, `history`, `created_at` and `updated_at`.

#### Scenario: The list skips what the operator never started

- **WHEN** a client creates a session and does not close a turn
- **THEN** `GET /answer/sessions` does not include that session
- **AND** `GET /answer/session/{id}` still returns it

#### Scenario: The title sticks to the first question

- **WHEN** the first closed question is a full subject and the second
  is a referential follow-up
- **THEN** the session title is the normalized first question
- **AND** a later `PATCH` with a non-empty title replaces it

#### Scenario: An expired session is absent from both list and rename

- **WHEN** the session's `updated_at` is older than
  `CONVERSATION_SESSION_TTL_DAYS`
- **THEN** `GET /answer/sessions` omits it
- **AND** `PATCH /answer/session/{id}` responds 404

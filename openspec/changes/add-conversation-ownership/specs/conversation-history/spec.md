# conversation-history Delta Specification

## MODIFIED Requirements

### Requirement: Sessions are titled and listable

`GET /answer/sessions` SHALL return summaries of conversations that
have at least one history turn and have not passed
`CONVERSATION_SESSION_TTL_DAYS`, newest `updated_at` first. Each
summary SHALL carry `session_id`, `title`, `created_at`, `updated_at`
and `turn_count`. Empty or expired sessions SHALL be omitted, not
returned as 404; an empty tenant SHALL return `[]`.

Pagination SHALL use `limit` (default 50, maximum 100) and `offset`.

The list is the **caller's own**. The caller's identity arrives in the
`X-Console-User` header, which only the BFF can send because only the
BFF holds the service token. A request without that header SHALL see
the conversations that have no owner either — absence of identity is
its own bucket and SHALL NOT be a wildcard, or the filter would be
turned off by dropping a header. The filter SHALL be applied in the
query, never to rows already read: filtering after a `limit` returns
short pages and a last page that lies.

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

A conversation SHALL carry an opaque `owner_id` — the console's user
id, never an email: the service SHALL NOT learn who anybody is to
resolve this authorization. `owner_id` SHALL NOT appear in
`SessionSummary` or `SessionView`.

Every route that takes a `session_id` SHALL scope by owner, not only
the list: `GET`, `PATCH` and `DELETE` of `/answer/session/{id}`, the
anchor `DELETE`, and both synthesis paths
(`/answer/agentic/start` and `resume`). Posting a turn into somebody
else's conversation is the same leak wearing a different hat.

On the session routes, somebody else's conversation SHALL be **404** —
the same `_UNKNOWN` the router already returns for unknown and for
expired. A 403 would confirm the id exists, which is information about
another person's activity.

On the synthesis paths a foreign `session_id` SHALL behave exactly like
an unknown one: the turn SHALL be answered without memory and nothing
SHALL be appended to that conversation. This keeps the contract
`open_turn` already has for an absent or expired id, where a mid-
conversation 404 would turn housekeeping into a dead end — and the
property that matters (no foreign transcript is read, no foreign
transcript is written) holds either way.

The TTL sweep SHALL NOT filter by owner: expiring is the clock's
business, not the caller's.

#### Scenario: The list is the caller's own
- **WHEN** two owners each have a conversation with closed turns
- **THEN** `GET /answer/sessions` returns one summary for each caller
- **AND** neither summary is the other owner's

#### Scenario: Reading somebody else's conversation
- **WHEN** a caller sends a `session_id` owned by another user
- **THEN** `GET /answer/session/{id}` responds 404
- **AND** `PATCH` and `DELETE` on that id also respond 404
- **AND** the conversation is not modified

#### Scenario: A turn cannot be posted into a conversation not one's own
- **WHEN** `/answer/agentic/start` is called with another owner's `session_id`
- **THEN** the turn is answered without that conversation's memory
- **AND** no turn is appended to that conversation

#### Scenario: No identity is not a wildcard
- **WHEN** a request arrives without `X-Console-User`
- **THEN** it lists only conversations that have no owner
- **AND** it does not list any conversation that has one

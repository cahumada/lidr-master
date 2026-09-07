# llm-usage-accounting Delta Specification

## ADDED Requirements

### Requirement: A chat completion SHALL carry provider-reported token usage

`Completion` SHALL include a `Usage` value with `input_tokens`,
`output_tokens`, `total_tokens` and `reported`. Both chat adapters
SHALL populate it from the provider payload: the OpenAI-compatible
wire from `usage.prompt_tokens` / `completion_tokens` /
`total_tokens`, the Anthropic Messages wire from
`usage.input_tokens` / `output_tokens` with `total_tokens` equal
to their sum.

A successful `complete()` SHALL log those three integers on the
existing `llm_complete` event. Callers SHALL keep substituting the
`LLM` Protocol with a test double; they SHALL NOT read a vendor
SDK object to learn usage.

#### Scenario: OpenAI-compatible usage is copied onto Completion

- **WHEN** a chat completion returns `usage` with prompt 100,
  completion 40 and total 140
- **THEN** `Completion.usage` is `input_tokens=100`,
  `output_tokens=40`, `total_tokens=140`, `reported=true`

#### Scenario: Anthropic usage is normalized to the same shape

- **WHEN** a Messages API response returns `usage` with
  `input_tokens=80` and `output_tokens=20` and no total
- **THEN** `Completion.usage.total_tokens` is 100
- **AND** `reported` is true

### Requirement: Missing provider usage SHALL be marked, not invented

If the provider omits `usage` or any token field is absent, the
adapter SHALL return `Usage(0, 0, 0, reported=false)` and SHALL
emit a warning (`llm_usage_missing`). It SHALL NOT fail the
completion, and it SHALL NOT guess tokens from character counts
or from `tiktoken`.

#### Scenario: A response without usage still returns the text

- **WHEN** a provider returns assistant text and no `usage` block
- **THEN** `Completion.text` is the assistant text
- **AND** `Completion.usage.reported` is false
- **AND** the three token fields are 0
- **AND** a `llm_usage_missing` warning is logged

### Requirement: Each successful HTTP completion SHALL persist one ledger row

A successful `complete()` on an HTTP answer path SHALL insert one
row into `llm_usage_events` with `tenant_id` (from settings, never
from the request), `purpose` (`answer` or `answer_synthesizer`),
`provider_id`, `model`, the three token fields, `reported`, and
nullable `session_id` / `thread_id`.

The insert SHALL happen at the call, not when the conversation
turn closes. A later human-review reject SHALL NOT delete the
row. A `complete()` that raises `LLMError` SHALL NOT insert a
row.

The generation eval path SHALL NOT write rows: `generate_answer`
receives a bare `LLM` and does not import the store.

#### Scenario: POST /answer writes one row when the model is called

- **WHEN** `POST /answer` gets a completion with reported usage
- **THEN** `llm_usage_events` gains one row with
  `purpose="answer"`, that model, and those token counts
- **AND** `session_id` and `thread_id` are null

#### Scenario: A second synthesis after an adjust is a second row

- **WHEN** an agentic run synthesizes, pauses at the gate, and
  resumes with `adjust` so the synthesizer runs again
- **THEN** two rows exist with `purpose="answer_synthesizer"`
  and the same `thread_id`

### Requirement: A skipped completion SHALL NOT write a ledger row

When generation returns the insufficient-context message without
calling the model — empty retrieval or a context budget that
kept nothing — the service SHALL NOT insert a row.

#### Scenario: Empty retrieval writes no event

- **WHEN** `POST /answer` finds no citations and returns the
  insufficient-context message
- **THEN** `llm_usage_events` gains no row for that request

### Requirement: A ledger write failure SHALL NOT fail the answer

If inserting the row raises, the service SHALL log
`llm_usage_record_failed` and SHALL still return the completion
to the caller. Losing an accounting row is a defect of the
ledger; dropping the answer because the insert failed is not.

#### Scenario: Store outage still returns the answer

- **WHEN** `RecordingLLM` finishes a successful `complete()` and
  `UsageStore.record` raises
- **THEN** the caller receives the `Completion` unchanged
- **AND** `llm_usage_record_failed` is logged

### Requirement: Answer HTTP responses SHALL carry the last completion usage

`POST /answer` (`AnswerResponse`) and the agentic completed,
paused and progress payloads SHALL include a `usage` object with
`input_tokens`, `output_tokens`, `total_tokens` and `reported`.
When the run called the model, `usage` SHALL match that last
`Completion.usage`. When it did not, `usage` SHALL be zeros with
`reported=false`.

A run that synthesized more than once SHALL expose the last
completion on the HTTP body; earlier calls remain on the ledger
only.

#### Scenario: A synthesized answer reports its usage

- **WHEN** the synthesizer completes with `reported=true` and
  total 140
- **THEN** the HTTP 200 body has `usage.total_tokens=140` and
  `usage.reported=true`

#### Scenario: Insufficient context reports unbilled zeros

- **WHEN** generation skips the model because nothing fit the
  context budget
- **THEN** the body has `usage.reported=false` and the three
  token fields equal 0

### Requirement: GET /usage/summary SHALL return tenant totals

`GET /usage/summary` SHALL return, for `Settings.TENANT_ID`,
`total_calls` and the three token sums, plus a `by_model` list
of `{provider_id, model, calls, input_tokens, output_tokens,
total_tokens}`. Optional query filters `from`, `to`,
`session_id` and `purpose` SHALL narrow the aggregate. `from`
later than `to` SHALL be 422. The tenant SHALL NOT be accepted
as a query parameter.

An empty window SHALL return zeros and an empty `by_model`, not
an error.

#### Scenario: Summary after two calls to the same model

- **WHEN** the ledger has two reported rows for `gpt-4o-mini`
  totaling 200 input and 80 output
- **THEN** `GET /usage/summary` returns `total_calls=2`,
  `input_tokens=200`, `output_tokens=80`, `total_tokens=280`
- **AND** `by_model` has one entry for that provider and model
  with the same counts

#### Scenario: Inverted time range is rejected

- **WHEN** `GET /usage/summary` is called with `from` later
  than `to`
- **THEN** the response is 422

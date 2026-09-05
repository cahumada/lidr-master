# agent-profiles Delta Specification

## ADDED Requirements

### Requirement: The catalog serves a worked example of the flow
`GET /config` SHALL include, inside `flow`, a worked example: one real
question with its provenance, and per node the input it receives and the
output it leaves in the state for that question. The example SHALL be
declared next to the catalog in the service, not in the console. Every
node served in `flow.nodes` SHALL carry both example fields — a node
without them would be a card the screen cannot explain.

#### Scenario: Every node carries its example
- **WHEN** the console reads `flow.nodes`
- **THEN** each node has a non-empty `example_input` and
  `example_output`

#### Scenario: The example names its source
- **WHEN** the console reads `flow.example`
- **THEN** it carries the question text and the identifier of the
  curated golden entry it was taken from

### Requirement: The deterministic part of the example cannot drift
The example of a deterministic agent SHALL be derived from the code that
agent runs, not written by hand. A test SHALL fail when the query
planner's example sub-queries stop matching `decompose()` applied to the
example question, or when its example filters stop matching
`_suggest_filters()`.

#### Scenario: Changing the decomposition breaks the example
- **WHEN** `decompose()` returns a different split for the example
  question
- **THEN** the catalog test fails instead of the screen showing a split
  the code no longer produces

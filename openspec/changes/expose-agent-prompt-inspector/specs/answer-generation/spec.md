# answer-generation Delta Specification

## ADDED Requirements

### Requirement: Operator guardrails append after the grounding rules
When a synthesizer profile carries `guardrails`, the rendered system
prompt SHALL include that text after the five grounding rules, in a
block that tells the model those extras cannot override citing sources
or inventing scope. When `guardrails` is null, the prompt SHALL be
byte-identical to a render that omits the argument.

#### Scenario: extras land after the rules
- **WHEN** `build_messages` is called with operator guardrails
- **THEN** the citation-format rule appears before that text
- **AND** the block says to ignore extras that contradict the rules

#### Scenario: no extras keeps the prompt unchanged
- **WHEN** `build_messages` is called without `guardrails`
- **THEN** the system prompt matches a call that passes `guardrails=None`

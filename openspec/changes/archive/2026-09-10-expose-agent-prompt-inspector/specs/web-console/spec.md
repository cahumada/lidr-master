# web-console Delta Specification

## ADDED Requirements

### Requirement: The agents screen shows the prompt, templates and tools
`/agents` SHALL show the synthesizer's system prompt as read-only text,
offer buttons that load the persona and operator-guardrails templates
into the matching fields without saving, let the operator edit both
fields, and show each agent's granted tools next to the tools it uses.
Deterministic agents SHALL show tools only — no prompt form.

#### Scenario: load the persona template
- **WHEN** the user clicks «Cargar template» on the persona field
- **THEN** the textarea fills with the senior insurance-analyst template
- **AND** the profile is not saved until the user confirms

#### Scenario: tools granted versus used
- **WHEN** the user looks at an agent card
- **THEN** they see tools disponibles (granted) and tools utilizadas
  (called)

# web-console Delta Specification

## ADDED Requirements

### Requirement: La pantalla de agentes enfoca un agente a la vez
`/agents` SHALL list the catalog as a picker and show the selected
agent's detail in a workspace. Configurable agents SHALL expose
named profiles one at a time. The system prompt, system guardrails
and the tools catalog SHALL remain available without occupying the
first screen. Deterministic agents SHALL stay read-only: role,
explanation and tools, no persona or model form.

#### Scenario: elegir un agente
- **WHEN** the operator picks a catalog entry
- **THEN** the workspace shows that agent's role, explanation and tools
- **AND** other agents' forms are not shown at the same time

#### Scenario: editar un perfil
- **WHEN** the operator picks a named profile of the synthesizer
- **THEN** they see that profile's persona, guardrails and model knobs
- **AND** the other profiles stay in the picker, not as stacked full forms

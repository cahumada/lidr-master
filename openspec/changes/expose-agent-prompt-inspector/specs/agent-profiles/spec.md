# agent-profiles Delta Specification

## ADDED Requirements

### Requirement: The catalog exposes the synthesizer prompt and system guardrails
`GET /config` SHALL include the rendered `answer/v1` system prompt without
operator extras, a list of system guardrails (the five prompt rules plus
the `check_grounding` check), a persona template for a senior insurance
functional analyst, and an operator-guardrails template. The five rules
and `check_grounding` SHALL NOT be writable through `/config`.

#### Scenario: the base prompt is visible
- **WHEN** a client reads `GET /config`
- **THEN** the synthesizer agent includes `system_prompt` containing the
  citation format and the insufficient-context sentence
- **AND** `system_guardrails` lists both prompt rules and the code check

#### Scenario: templates are offered
- **WHEN** a client reads `GET /config`
- **THEN** `persona_template` describes a senior insurance functional
  analyst
- **AND** `guardrails_template` lists extra operator constraints

### Requirement: Tools are reported as granted and as used
Each agent in `GET /config` SHALL report `tools` (from the privilege
table) and `tools_used` (the tools that node actually calls). The
response SHALL also include a global `tools` catalog with name,
description, `granted_to` and `used_by`. The console SHALL NOT persist
a tool allowlist.

#### Scenario: the retriever grants and uses search_corpus
- **WHEN** a client reads the `evidence_retriever` agent
- **THEN** `tools` and `tools_used` both contain `search_corpus`

#### Scenario: the synthesizer has no tools
- **WHEN** a client reads the `answer_synthesizer` agent
- **THEN** `tools` and `tools_used` are empty

### Requirement: Operator guardrails on a named profile
A named profile SHALL persist an optional `guardrails` text, capped at
the same limit as `persona`. A null value SHALL mean "no operator
guardrails". The text SHALL be appended to the system prompt after the
five rules and SHALL be declared subordinate to them. A value over the
cap SHALL be refused with 422.

#### Scenario: operator guardrails are stored and reported
- **WHEN** a profile is written with `guardrails` under the cap
- **THEN** `GET /config` returns that text on the profile
- **AND** the effective sources report `guardrails` as `profile`

#### Scenario: over-cap guardrails are refused
- **WHEN** a profile is written with `guardrails` longer than the cap
- **THEN** the service responds 422 and stores nothing

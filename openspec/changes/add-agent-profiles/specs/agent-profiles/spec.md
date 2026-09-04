# agent-profiles Delta Specification

## ADDED Requirements

### Requirement: The service owns the agent catalog

The service SHALL serve, over `GET /config`, one entry per node of the answer
graph with its key, label, role, explanation, kind, whether it is LLM-driven,
and the tools it may call. The tool list SHALL be derived from the privilege
table the dispatcher enforces, not declared a second time. The web console
SHALL render its agents screen from this response rather than declaring the
graph again on its side.

#### Scenario: Catalog covers exactly the graph's nodes

- **WHEN** the catalog is compared against the compiled graph's node names
- **THEN** they are the same set, so a node added or renamed without a catalog
  entry fails the suite instead of disappearing from the console

#### Scenario: Tools come from the privilege table

- **WHEN** an agent's tools are reported
- **THEN** they are exactly that agent's allowlist in `AGENT_PRIVILEGES`, and
  only `evidence_retriever` reports one

### Requirement: Per-agent overrides of persona, model and sampling

The service SHALL persist, per agent, an optional `persona`, `model`,
`temperature` and `max_tokens`. Every knob SHALL be nullable, and a null knob
SHALL mean "use the service default" so that clearing a field is a real
operation. `GET /config` SHALL report, for each effective value, whether it
came from the profile or from the settings.

#### Scenario: A partial profile only overrides what it sets

- **WHEN** a profile sets a persona but no model
- **THEN** the effective config carries that persona and the settings' model,
  and reports the sources as `profile` and `settings` respectively

#### Scenario: A temperature of zero from a profile is an override

- **WHEN** a profile stores `temperature = 0.0` and the settings' default is
  higher
- **THEN** the effective temperature is `0.0` and its source is `profile`,
  because a deliberate zero is not an absent value

#### Scenario: Overrides survive a redeploy

- **WHEN** a profile is written and the service restarts
- **THEN** the profile still applies, because it lives in the database and not
  in the container's filesystem

### Requirement: Only agents that call a model may be configured

The service SHALL reject a write to a deterministic agent's profile with HTTP
422, and an unknown agent with HTTP 404. It SHALL reject a model outside the
served catalog and a persona over the configured cap, both with HTTP 422. A
setting that the service would ignore SHALL NOT be accepted and stored.

#### Scenario: Configuring a deterministic agent is refused

- **WHEN** a persona is written for `query_planner`, which calls no model
- **THEN** the service responds 422 explaining that the agent is deterministic,
  and stores nothing

#### Scenario: A model outside the catalog is refused

- **WHEN** a model that the catalog does not list is written
- **THEN** the service responds 422 and names the models it accepts

### Requirement: A persona changes the voice, never the grounding rules

The persona SHALL be appended to the synthesizer's system prompt after the
grounding rules, together with an instruction that the rules win if the two
conflict. With no persona configured, the rendered prompt SHALL be identical to
the prompt before this capability existed, so measured generation evals stay
comparable.

#### Scenario: No persona leaves the prompt untouched

- **WHEN** the messages are built with no persona
- **THEN** the system prompt is byte-identical to the one built without the
  argument at all

#### Scenario: A persona is subordinate to the rules

- **WHEN** a persona is configured
- **THEN** it appears after the citation rules in the system prompt, preceded by
  an instruction to ignore it wherever it would conflict with them

### Requirement: One resolution point for every synthesis path

`POST /answer`, `POST /answer/agentic` and the background runner SHALL all
resolve the synthesizer's LLM and persona through the same function, and the
graph SHALL receive both through its runnable config. An agent SHALL NOT read
the profile store itself.

#### Scenario: A configured persona applies to both endpoints

- **WHEN** a persona is configured and a question is asked through either the
  synchronous or the agentic endpoint
- **THEN** both use it, because neither builds its own LLM

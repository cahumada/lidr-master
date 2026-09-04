# agent-profiles Delta Specification

## ADDED Requirements

### Requirement: Named profiles per configurable agent
The service SHALL persist zero or more named profiles per configurable
agent. Each profile SHALL have a `name` unique among that agent's
profiles, an optional `persona`, optional model knobs (`provider`,
`model`, `temperature`, `max_tokens`), and an `is_default` flag. A null
knob SHALL still mean "use the service default". At most one profile per
agent SHALL be the default. Deterministic agents SHALL have no profiles.

#### Scenario: Two named presets on the synthesizer
- **WHEN** profiles named `Conservador` and `Exhaustivo` are created for
  `answer_synthesizer`
- **THEN** `GET /config` lists both under that agent
- **AND** each keeps its own persona and model knobs

#### Scenario: Duplicate name is refused
- **WHEN** a second profile with the same name (case-insensitive) is
  written for the same agent
- **THEN** the service responds 422 and stores nothing

#### Scenario: A deterministic agent still cannot hold a profile
- **WHEN** a named profile is written for `query_planner`
- **THEN** the service responds 422 explaining the agent is deterministic

### Requirement: Exactly one default, or none
Creating or updating a profile with `is_default` true SHALL clear the
flag on every other profile of that agent. Deleting the default SHALL
promote another profile if one remains, or leave the agent on service
defaults if none remain. An agent with no profiles SHALL behave as it
did before named profiles existed.

#### Scenario: Marking a profile default unsets the previous one
- **WHEN** `Exhaustivo` is marked default while `Conservador` was
- **THEN** only `Exhaustivo` reports `is_default`

#### Scenario: Deleting the last profile falls back to settings
- **WHEN** the only profile of the synthesizer is deleted
- **THEN** the next synthesis uses the service default model and no
  persona

### Requirement: The catalog also serves the graph topology
`GET /config` SHALL include a `flow` object with the graph's nodes,
each node's `kind`, the outgoing edges declared by the compiled graph,
and the orchestrator's fallback ladder. The web console SHALL render
its flow screen from this object rather than declaring the graph again.
A test SHALL fail if `flow` drifts from the compiled graph or from the
orchestrator's `_ORDER`.

#### Scenario: Flow matches the compiled graph
- **WHEN** the served `flow` is compared to the compiled graph's node
  names and edges
- **THEN** they are the same set

#### Scenario: Ladder matches the orchestrator
- **WHEN** the served `flow.ladder` is compared to the orchestrator's
  fallback order
- **THEN** they are the same sequence

## MODIFIED Requirements

### Requirement: Per-agent overrides of persona, model and sampling
The service SHALL persist persona and model knobs on **named profiles**
of a configurable agent, not on a single anonymous row keyed only by
`agent_key`. Every knob SHALL remain nullable, and a null knob SHALL
mean "use the service default". `GET /config` SHALL report, for the
profile in force (the default, or a requested id), whether each
effective value came from that profile or from the settings. An existing
anonymous row SHALL be migrated to a default profile named `Default`;
an agent with no row SHALL not receive an invented profile.

#### Scenario: A partial profile only overrides what it sets
- **WHEN** a named profile sets a persona but no model
- **THEN** the effective config carries that persona and the settings'
  model, and reports the sources as `profile` and `settings` respectively

#### Scenario: A temperature of zero from a profile is an override
- **WHEN** a profile stores `temperature = 0.0` and the settings'
  default is higher
- **THEN** the effective temperature is `0.0` and its source is
  `profile`, because a deliberate zero is not an absent value

#### Scenario: Overrides survive a redeploy
- **WHEN** a named profile is written and the service restarts
- **THEN** the profile still applies, because it lives in the database
  and not in the container's filesystem

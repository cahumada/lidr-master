# agent-profiles Specification

## Purpose

El catálogo de agentes que el servicio sirve por `GET /config`: qué agentes
existen, qué herramientas puede llamar cada uno, cómo se configuran y resuelven
su persona y sus knobs de modelo, qué proveedores y modelos hay disponibles, y
la topología del grafo con su recorrido de ejemplo.

Implementado en `app/domain/profiles.py` (perfiles nombrados),
`app/domain/providers_store.py` (proveedores y modelos en la base),
`app/domain/graph/catalog.py` (el catálogo y el flujo),
`app/foundation/llm/` (los adaptadores), `app/foundation/secrets.py` (el cifrado
de credenciales) y `app/api/config.py` (el transporte).

Promovido de: `add-agent-profiles`, `add-multi-provider-llm`,
`add-dynamic-providers`, `add-named-agent-profiles-and-flow`,
`add-flow-worked-example`, `expose-agent-prompt-inspector`.

**Dos límites declarados**, que son propiedades del sistema de hoy y no
aspiraciones pendientes:

- Los adaptadores de **Anthropic y Moonshot** están probados contra dobles y
  contra la forma documentada del SDK, **no contra una respuesta real**: en este
  entorno no hay claves de esos dos proveedores. Es la razón por la que
  `add-multi-provider-llm` y `add-dynamic-providers` siguen en curso, aunque su
  código esté escrito.
- **El servicio no tiene autenticación**, así que el endpoint que escribe
  credenciales lo puede llamar cualquiera que lo alcance (escribir, no leer).
  Autenticar el servicio es su propio change y debería preceder a exponerlo en
  internet.

## Requirements

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
example question, or when its example filters stop matching what the planner
resolves for that question.

The guard used to name `_suggest_filters()` — the heuristic that read filter
hints out of the question's text. That heuristic is gone (it emitted a
vocabulary the corpus does not have), so the guard now runs the **node** rather
than a private helper. The example's claim that `filters` comes out empty is now
structural: with no request filters and no anchors there is nothing to resolve.

#### Scenario: Changing the decomposition breaks the example
- **WHEN** `decompose()` returns a different split for the example
  question
- **THEN** the catalog test fails instead of the screen showing a split
  the code no longer produces

#### Scenario: A filter the example does not claim breaks it too
- **WHEN** the planner resolves any filter for the example question
- **THEN** the catalog test fails, because the example text states that
  `filters` comes out empty
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

### Requirement: One resolution point for every synthesis path
`POST /answer`, `POST /answer/agentic` and the background runner SHALL all
resolve the synthesizer's LLM and persona through the same function, and the
graph SHALL receive both through its runnable config. An agent SHALL NOT read
the profile store itself.

#### Scenario: A configured persona applies to both endpoints
- **WHEN** a persona is configured and a question is asked through either the
  synchronous or the agentic endpoint
- **THEN** both use it, because neither builds its own LLM

### Requirement: Three generation providers behind two adapters
The service SHALL support OpenAI, Anthropic and Moonshot (Kimi) as generation
providers. Providers that serve an OpenAI-compatible API SHALL share one
adapter, distinguished only by base URL and key; Anthropic SHALL have its own
adapter that absorbs the Messages API's shape (`system` as a request
parameter, a required `max_tokens`, and a response of content blocks).

#### Scenario: Moonshot reuses the OpenAI adapter
- **WHEN** an LLM is built for Moonshot
- **THEN** it is the OpenAI-compatible adapter pointed at Moonshot's base URL,
  not a third implementation of the same wire format

#### Scenario: Anthropic sends the system prompt as a parameter
- **WHEN** the Anthropic adapter completes a system + user pair
- **THEN** the system text travels as the request's `system` parameter and the
  messages carry only the user turn

#### Scenario: A policy decline is an error, not an empty answer
- **WHEN** Anthropic returns HTTP 200 with `stop_reason == "refusal"` and no
  text
- **THEN** the adapter raises, because returning an empty string would read as
  "the model had nothing to say"

### Requirement: Providers and models are editable rows, seeded from code
The service SHALL store providers and their models in the database and SHALL
seed them from the built-in registry and `ANSWER_MODEL_CATALOG` at startup.
Seeding SHALL be idempotent and additive: it inserts what is missing and never
overwrites an existing row, so an edit made from the console survives every
restart. A failure to seed SHALL NOT prevent the service from starting.

#### Scenario: A fresh install behaves as it did before the tables existed
- **WHEN** the service starts against a database with no provider rows
- **THEN** the built-in providers and the catalog from the settings are
  inserted, and the console offers the same models the setting listed

#### Scenario: A restart does not undo curation
- **WHEN** a model has been hidden from the console and the service restarts
- **THEN** the model is still hidden, because seeding never overwrites a row

#### Scenario: A provider speaking an implemented wire needs no code change
- **WHEN** a provider row declares a wire the service implements and a base URL
- **THEN** its models can be selected and answered with, without a deploy

#### Scenario: A wire no adapter implements is rejected
- **WHEN** a client for a provider whose wire is not implemented is requested
- **THEN** the service raises rather than attempting the call

### Requirement: The model catalog can be read from the provider
The service SHALL expose an endpoint that asks a provider which models it
serves and stores the ones not already known. Newly discovered models SHALL be
stored **hidden**, and existing rows SHALL be left untouched. The endpoint
SHALL refuse when the provider has no usable credential, and SHALL report a
provider-side failure as a bad gateway rather than a success with no models.

#### Scenario: Discovered models arrive hidden
- **WHEN** a refresh reports models the database did not have
- **THEN** they are stored with `visible` false, because a provider's listing
  includes models that are not chat models at all

#### Scenario: A refresh does not resurrect a hidden model
- **WHEN** a refresh reports a model that a human had hidden
- **THEN** the row keeps its curation and is counted as already known

#### Scenario: Refreshing without a credential is refused
- **WHEN** a refresh is requested for a provider with no usable credential
- **THEN** the service responds 422 rather than attempting the call

### Requirement: Hidden models are refused on write, not only in the dropdown
A model marked not visible SHALL be rejected when an agent profile selects it.
Honouring curation only in the console's dropdown would make the API the way
around it.

#### Scenario: Selecting a hidden model is refused
- **WHEN** an agent profile is written naming a model whose row is hidden
- **THEN** the service responds 422 and lists the models it does offer

### Requirement: Sampling support is a property of the model
The service SHALL treat acceptance of `temperature` as a per-model capability
and SHALL publish it in the model catalog. When a model does not accept
sampling parameters, the service SHALL omit `temperature` from the request
rather than send it and receive an error, and SHALL log the omission.

#### Scenario: A model that rejects sampling gets no temperature
- **WHEN** an LLM is built for a model that rejects sampling parameters, with a
  temperature configured
- **THEN** the adapter receives no temperature, and the omission is logged

#### Scenario: Two models of the same provider can differ
- **WHEN** the catalog reports capabilities for `claude-sonnet-5` and
  `claude-haiku-4-5`
- **THEN** the first says it does not accept `temperature` and the second says
  it does — the capability is not inherited from the provider

#### Scenario: The effective config reports "unsupported" rather than a number
- **WHEN** an agent's effective configuration is read for a model that rejects
  sampling
- **THEN** its temperature is null and its source is `unsupported`, so the
  console does not display a value that is not being sent

### Requirement: A model's sampling capability is stored and correctable
`supports_temperature` SHALL be stored per model row, seeded from what the code
knows, and editable afterwards. A model the code has never seen SHALL still be
correctable without a deploy.

#### Scenario: A capability can be corrected from the console
- **WHEN** a model's `supports_temperature` is set to false
- **THEN** the effective configuration for an agent using it reports no
  temperature, and no temperature is sent to the provider

### Requirement: A provider without credentials is rejected before use
`GET /config` SHALL report each provider's availability, derived from whether
its API key is configured. A write selecting a model whose provider is
unavailable SHALL be rejected with HTTP 422 naming the missing setting, rather
than stored to fail at answer time.

#### Scenario: Selecting an unconfigured provider is refused
- **WHEN** a profile is written with a provider that has no API key
- **THEN** the service responds 422 naming that provider's key setting, and
  stores nothing

### Requirement: Provider and model are stored and validated as a pair
The profile SHALL store the provider in its own column alongside the model, and
the service SHALL validate the pair against the catalog. A provider sent
without a model SHALL be rejected, and a pair absent from the catalog SHALL be
rejected, both with HTTP 422.

#### Scenario: A model under the wrong provider is refused
- **WHEN** a profile is written pairing a provider with a model it does not
  serve, where both exist separately in the catalog
- **THEN** the service responds 422 and lists the pairs it does offer

#### Scenario: The stored pair survives together
- **WHEN** a profile stores a provider and model that differ from the service
  defaults
- **THEN** the effective configuration reports both as coming from the profile,
  and the model is never read against the default provider

### Requirement: Embeddings stay on one provider
The corpus embeddings SHALL NOT be provider-configurable. The stored vectors
belong to one embedding model's space, so changing the embedding provider is a
corpus rebuild and not a setting; the multi-provider catalog SHALL apply to
answer generation only.

#### Scenario: The catalog does not offer embedding models
- **WHEN** the model catalog is read
- **THEN** it contains generation models only, and the embedding model remains
  configured by its own setting

### Requirement: Stored credentials are encrypted with an environment master key
Provider credentials MAY be stored in the database, encrypted with a master key
that lives in the environment and never in the database. With no master key
configured, storing a credential SHALL fail with a clear error. The service
SHALL NOT provide any path that stores a credential in the clear.

#### Scenario: Without a master key, storing is refused
- **WHEN** a credential is submitted and no master key is configured
- **THEN** the service responds 409 naming the missing setting, and stores
  nothing

#### Scenario: The catalog reports whether storage is possible
- **WHEN** the configuration is read
- **THEN** it states whether credential storage is enabled, so the console does
  not offer a form that would fail

#### Scenario: An unreadable credential is treated as absent
- **WHEN** a stored ciphertext cannot be decrypted with the current master key
- **THEN** the provider is reported as having no credential, rather than a
  broken value being sent to it

### Requirement: No endpoint returns a stored credential
No endpoint SHALL return a credential, decrypted or otherwise. The service MAY
return the source of the credential in force and at most a short hint derived
from it, sufficient to tell two credentials apart.

#### Scenario: A credential does not appear in any response
- **WHEN** a credential is stored and then the configuration, the provider and
  the clear-credential responses are read
- **THEN** none of those bodies contains the submitted value

#### Scenario: The source of the credential in force is reported
- **WHEN** a provider holds a credential
- **THEN** the response says whether it came from the environment or from
  storage, so an operator knows where to change it

### Requirement: An environment credential wins over a stored one
When both an environment variable and a stored credential exist for a
provider, the service SHALL use the environment one and SHALL report it as the
source in force.

#### Scenario: Storing does not override the environment
- **WHEN** a credential is stored for a provider whose environment variable is
  set
- **THEN** the provider still reports the environment as its source, so a
  deployment using real secret management is not silently overridden

<!-- Promovido de: fix-module-filter-vocabulary -->

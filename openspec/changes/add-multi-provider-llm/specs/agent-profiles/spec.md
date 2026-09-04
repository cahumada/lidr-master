# agent-profiles Delta Specification

## ADDED Requirements

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

# agent-profiles Delta Specification

## ADDED Requirements

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

### Requirement: A model's sampling capability is stored and correctable

`supports_temperature` SHALL be stored per model row, seeded from what the code
knows, and editable afterwards. A model the code has never seen SHALL still be
correctable without a deploy.

#### Scenario: A capability can be corrected from the console

- **WHEN** a model's `supports_temperature` is set to false
- **THEN** the effective configuration for an agent using it reports no
  temperature, and no temperature is sent to the provider

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

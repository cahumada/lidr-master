# answer-orchestration Delta Specification

## ADDED Requirements

### Requirement: A run may select the synthesizer profile
`POST /answer` and `POST /answer/agentic` SHALL accept an optional
`profile_id`. When present, the shared synthesizer runtime SHALL resolve
that named profile and SHALL reject an unknown id or one that does not
belong to `answer_synthesizer` with HTTP 422. When absent, the runtime
SHALL use the synthesizer's default profile, or the service settings if
none exists. The graph SHALL still receive the resolved LLM and persona
through its runnable config and SHALL NOT read the profile store.

#### Scenario: Default profile applies without an id
- **WHEN** a default named profile is stored and a question is asked
  without `profile_id`
- **THEN** both the synchronous and the agentic endpoints use that
  profile's persona and model knobs

#### Scenario: An explicit id overrides the default for one run
- **WHEN** a request names a non-default profile of `answer_synthesizer`
- **THEN** that run uses it
- **AND** later runs without an id still use the default

#### Scenario: A foreign or unknown profile is refused
- **WHEN** the request carries a `profile_id` that does not exist or
  belongs to another agent
- **THEN** the endpoint responds 422 and does not invoke the graph

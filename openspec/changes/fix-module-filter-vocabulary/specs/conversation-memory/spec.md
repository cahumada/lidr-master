# conversation-memory Delta Specification

## MODIFIED Requirements

### Requirement: The window holds recent turns, anchors hold pinned constraints
The session SHALL keep at most `CONVERSATION_MAX_TURNS` (question, answer)
pairs, evicting whole pairs. A turn where the user pins a scope constraint —
a transaction prefix, a window type — SHALL be promoted to `anchors`, which the
sliding window never evicts.

An anchor SHALL apply as a default filter on later turns and SHALL be
reported in the response. A filter applied without saying so is a defect,
not a convenience.

**«Módulo CA» pins a transaction prefix, not a `module_code`.** The word means
two different things: for a person the module of `CA014` is «CA», and for the
corpus its `module_code` is `DMECAR` — the module node of the `WINDOWS` tree the
breadcrumb came from. Both are true, and translating one into the other is not
possible without guessing: of the corpus's 71 code prefixes, several span
multiple modules (`OPL` covers five, `MA` covers four), so picking the dominant
one would drop the tail.

So the pin is applied to the dimension the user actually named — the documents
whose code starts with that prefix — and reported as such. Nothing is inferred:
`module_code` remains the dimension the console's selector uses, with the
vocabulary `GET /search/facets` serves.

#### Scenario: The window evicts whole pairs
- **WHEN** the session holds `CONVERSATION_MAX_TURNS` pairs and a new turn
  closes
- **THEN** the oldest pair is evicted whole
- **AND** a question is never kept without its answer

#### Scenario: A pinned filter outlives the window
- **WHEN** the user pins a scope and then runs more turns than the window
  holds
- **THEN** the pinned filter still applies
- **AND** the response reports which anchors were applied

#### Scenario: An anchor can be removed
- **WHEN** the user removes a pinned filter from the console
- **THEN** later turns are retrieved without it

#### Scenario: A module pin narrows by transaction prefix
- **WHEN** the user pins «solo módulo CA» and asks a later question
- **THEN** the turn retrieves documents whose code starts with `CA`
- **AND** the response reports the anchor as a transaction prefix, not as a
  `module_code`

#### Scenario: A pin never silently empties the conversation
- **WHEN** a pinned value cannot be resolved to a dimension the store can filter
- **THEN** it is not applied
- **AND** the response says so, instead of returning no evidence for every
  later turn

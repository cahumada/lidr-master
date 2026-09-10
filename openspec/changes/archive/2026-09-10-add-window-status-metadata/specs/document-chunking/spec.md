# document-chunking Delta Specification

## MODIFIED Requirements

### Requirement: Chunk metadata SHALL carry the transaction's type and navigation breadcrumb
Retrieval cannot filter by module or transaction type unless the metadata
carries them. The breadcrumb fields SHALL be flat rather than nested, since the
vector store filters by equality, and every one SHALL be optional: the `WINDOWS`
export resolves a path for only part of the corpus (54.2% of documents), and an
unresolved breadcrumb must read as unresolved rather than as a guess.

The same export also declares the window's **status**, and 1.624 of its 3.389
windows are not the active one. A chunk SHALL carry that status when the tree
resolves it, for the same reason it carries the type: the consumer cannot tell
current functionality from functionality the source system no longer serves
unless the metadata says so.

#### Scenario: Metadata on a classified transaction
- **WHEN** a chunk is produced for a transaction whose type and path resolve
- **THEN** its metadata carries `transaction_type`, `module_code` and `module_name`
- **AND** `submodule_code` / `submodule_name` when the path has that level

#### Scenario: Metadata when the taxonomy cannot be resolved
- **WHEN** the type is `unknown` or the breadcrumb is unresolved
- **THEN** those fields are absent or explicitly unknown
- **AND** no value is fabricated to fill them

#### Scenario: Each transaction in a multi-transaction file carries its own type
- **WHEN** a file describes a transaction and its `_k` companion
- **THEN** the main one carries its own type (e.g. `functional_abm`)
- **AND** the companion carries `key_request`

#### Scenario: The declared window status travels with the chunk
- **WHEN** the tree resolves a status for the chunk's transaction code
- **THEN** the metadata carries `window_status` with the declared name
- **AND** an unresolved status leaves the field absent, never defaulted to active

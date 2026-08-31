# document-ingestion-api Specification

## Purpose
Expose the chunking pipeline over HTTP. Two entry points on the same
underlying logic: a JSON body for programmatic callers, and a file upload for
manual testing from Swagger UI. Implemented in `app/api/documents.py`, wired in
`app/main.py`, with contracts in `app/generation/rag/schemas.py`.

## Requirements

### Requirement: The router SHALL carry no business logic
The router's job is transport and error mapping. Chunking logic lives in the
chunking capability; the chunker is injected as a dependency from the
composition root (`app/dependencies.py`) rather than constructed in the router.

#### Scenario: Chunker injected
- **WHEN** an ingest endpoint handles a request
- **THEN** it obtains the chunker through FastAPI dependency injection
- **AND** both endpoints share one implementation of the ingest body

### Requirement: POST /documents/ingest SHALL accept the document text in a JSON body
`content` is the raw markdown TEXT. The service never reads from disk, so a
filesystem path in `content` is treated as the document's entire content — it
will parse to no sections and yield zero chunks. The field description states
this, since it is the most likely caller mistake.

#### Scenario: Valid JSON body
- **WHEN** a request carries `filename` and `content` with the raw markdown
- **THEN** the response is `200` with the document's id, title, chunks and stats

#### Scenario: Missing or empty fields
- **WHEN** `filename` or `content` is absent or empty
- **THEN** FastAPI returns `422` from Pydantic validation

### Requirement: POST /documents/ingest-file SHALL accept a file upload
A raw markdown file is impractical to paste and escape into a JSON body by
hand, and Swagger UI renders a native file picker for an upload parameter. The
uploaded bytes SHALL be decoded as UTF-8.

#### Scenario: UTF-8 markdown upload
- **WHEN** a `.md` file encoded in UTF-8 is uploaded
- **THEN** the response is `200` and equivalent to passing the same text to `/documents/ingest`

#### Scenario: File that is not UTF-8
- **WHEN** the uploaded bytes cannot be decoded as UTF-8
- **THEN** the response is `400` stating the file must be UTF-8 encoded markdown

### Requirement: The response contract SHALL be fully typed
`metadata` and `stats` SHALL be nested Pydantic models, not bare `dict`. A bare
`dict` renders as an empty `object` in Swagger's Schema tab and as a generic
`additionalProp1` placeholder in Example Value, hiding the real attributes from
anyone reading the docs.

The response SHALL carry a LIST of documents rather than a single document's
fields, because one source file can describe several transactions. A
single-transaction file yields a list of one, so callers have one shape to
handle instead of two.

#### Scenario: Schema exposes real attributes
- **WHEN** the OpenAPI schema is generated
- **THEN** `ChunkMetadata` declares `document_id`, `document_title`, `section`,
  `chunk_type`, `transaction_type`, `document_kind`, `module_code`,
  `module_name`, `submodule_code`, `submodule_name`, `field` and `bullet_path`
- **AND** `IngestStats` declares `total_documents`, `total_chunks`,
  `total_tokens`, `table_chunks` and `narrative_chunks`

#### Scenario: Single-transaction file
- **WHEN** a file describing one transaction is ingested
- **THEN** the response carries `source_file` and a `documents` list of one entry
- **AND** `stats.total_documents` is 1

#### Scenario: Multi-transaction file
- **WHEN** a file describing a transaction and its `_k` companion is ingested
- **THEN** `documents` carries one entry per transaction
- **AND** the `_k` entry carries `parent_transaction_code` naming its main transaction

#### Scenario: Stats reflect the produced chunks
- **WHEN** a document is ingested
- **THEN** `stats` reports the chunk total across all documents, the summed
  token count, and the split between table and narrative chunks

### Requirement: A chunking failure SHALL return 500 with the detail logged
An unexpected failure SHALL yield a generic client message while the real
error type and message are logged, so a malformed document never leaks internals
to the caller nor disappears from the logs.

#### Scenario: Chunker raises
- **WHEN** the chunker raises for a given document
- **THEN** the response is `500` with a generic detail
- **AND** the filename, error type and truncated error message are logged

### Requirement: Liveness SHALL be observable without side effects
`GET /health` SHALL answer without touching the chunker or any external
dependency.

#### Scenario: Health probe
- **WHEN** `GET /health` is called
- **THEN** the response is `200` with `{"status": "ok"}`

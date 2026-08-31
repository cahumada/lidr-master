# corpus-batch-chunking Specification

## Purpose
Run the chunker over the whole functional-spec corpus offline and report what
happened, so the full 30-module corpus can be chunked in one pass and every
anomaly is visible. Implemented in `scripts/chunk_corpus.py`.

## Requirements

### Requirement: The corpus SHALL be discovered by walking module directories
The corpus root holds one directory per business module (`policies`, `life`,
`claims`, `maintenance`, ...), each with its own `.md` files, and some modules
carry nested subdirectories. Discovery SHALL walk recursively and group every
file under its top-level module directory.

#### Scenario: Recursive discovery grouped by module
- **WHEN** the script runs against the corpus root
- **THEN** every `.md` file below the root is grouped under its top-level module directory

#### Scenario: Module filter
- **WHEN** `--modules` names one or more modules
- **THEN** only those modules are processed

### Requirement: Project documentation at the corpus root SHALL NOT be chunked
The corpus root also holds documentation about the corpus itself
(`processing_report.md`, `prompt_procesamiento_rag.md`). These are not
transaction documents and SHALL be excluded, so they never enter the RAG as if
they were functional specs.

#### Scenario: Root-level project docs excluded
- **WHEN** discovery encounters those files directly at the root
- **THEN** they are skipped

### Requirement: One bad file SHALL NOT abort the run
The corpus contains genuinely broken files, so a single failure SHALL be
caught, attributed to its path, and counted — never allowed to end the batch
and lose the other thousands of documents.

#### Scenario: File that cannot be decoded
- **WHEN** a file is not valid UTF-8
- **THEN** it is recorded as a failure with its path and reason
- **AND** the run continues with the remaining files

#### Scenario: File that raises during chunking
- **WHEN** the chunker raises for a file
- **THEN** the failure is recorded with the exception type and message
- **AND** the run continues

### Requirement: Chunks SHALL be written as one JSON file per module
Output SHALL be grouped per module rather than one monolithic file, so a single
module can be regenerated or inspected without rewriting the whole corpus.

#### Scenario: Per-module output
- **WHEN** a module finishes
- **THEN** `<out>/<module>.json` is written, holding the module name and one
  entry per document with its `source_file`, `document_id`, `document_title` and chunks

### Requirement: The generated corpus SHALL have a declared on-disk shape
`data/chunks/` is the artifact the embedding layer will consume, so its shape is
part of the contract rather than a detail of the script. Each `<module>.json`
carries two top-level keys, `module` and `documents`; each entry of `documents`
is a serialized `ChunkedDocument` plus two provenance fields the model does not
carry, because they belong to the run and not to the transaction:
`source_file` and `module`.

#### Scenario: One JSON per module
- **WHEN** the batch run finishes
- **THEN** a `<out>/<module>.json` exists per processed module, carrying
  `module` and `documents`

#### Scenario: Provenance and taxonomy are persisted
- **WHEN** a document entry is written
- **THEN** it carries `source_file` and `module` alongside the `ChunkedDocument` fields
- **AND** the taxonomy fields (`transaction_type`, `document_kind`,
  `child_links`, `navigation_path`, `is_menu_node`, `parent_transaction_code`,
  `is_container`) are persisted, not only the chunks' metadata

### Requirement: One source file SHALL be able to contribute several document entries
Output is grouped by transaction, not by file: a file describing a transaction
and its `_k` companion contributes two entries sharing one `source_file`. A
consumer assuming one entry per file would lose transactions.

#### Scenario: Multi-transaction file
- **WHEN** a file declares two transactions
- **THEN** it contributes two `documents` entries, same `source_file`,
  different `document_id`

### Requirement: The navigation tree input SHALL be a declared CSV artifact
The tree enters the pipeline as `data/windows_tree.csv` with three columns:
`code`, `parent_code`, `description`. It is the conversion of a `WINDOWS` table
export, reproducible with `scripts/import_windows_tree.py`. It is a versioned
data artifact, not a cache: it is a partial snapshot of one installation, and
its coverage limits how much breadcrumb resolves.

#### Scenario: CSV columns
- **WHEN** the pipeline loads the tree
- **THEN** it reads `code`, `parent_code` and `description`
- **AND** a row with no `code` is ignored

#### Scenario: Reproducible conversion
- **WHEN** the same export is converted twice
- **THEN** the resulting CSV is identical

#### Scenario: No CSV present
- **WHEN** the file does not exist at the configured path
- **THEN** the run proceeds without resolving any breadcrumb, without failing

### Requirement: The run SHALL emit a report naming every anomaly
Counts alone would hide the two failure modes worth a human's attention: a file
that parsed but produced nothing, and a file that raised. Both SHALL be listed
individually by path, not merely totalled.

The report SHALL also carry the document count, which can exceed the file
count: the difference is the transactions that were hidden inside
multi-transaction files, and it is a coverage figure, not an arithmetic error.

#### Scenario: Report contents
- **WHEN** the run completes
- **THEN** `<out>/chunking_report.md` holds a per-module table of files,
  documents, chunks, tokens, and the table/narrative split
- **AND** every zero-chunk file is listed by path with its resolved `document_id`
- **AND** every failed file is listed by path with its error

#### Scenario: More documents than files
- **WHEN** a module contains multi-transaction files
- **THEN** its document count exceeds its file count, and that is correct

#### Scenario: Zero-chunk file is surfaced, not silently accepted
- **WHEN** a file yields no chunks
- **THEN** it is counted and listed in the report for review

### Requirement: La corrida DEBE emitir un manifiesto del corpus
Sin manifiesto, los JSON por módulo son una pila de chunks sin procedencia: no
dicen de qué cliente son, de qué versión de la documentación, ni cuándo se
generaron. El manifiesto (`<out>/manifest.json`) es la declaración autoritativa
de esa corrida, replicando el `manifest` de `corpus_schema.json`.

#### Scenario: Contenido del manifiesto
- **WHEN** la corrida termina
- **THEN** `<out>/manifest.json` lleva `corpus_id`, `tenant_id`, `doc_version`,
  `generated_at`, `source_root`, los módulos procesados y los totales de
  documentos, chunks y tokens

#### Scenario: Identidad sobreescribible por corrida
- **WHEN** la corrida recibe `--tenant` o `--doc-version`
- **THEN** esos valores se usan en el estampado y en el manifiesto, en vez de
  los de la configuración

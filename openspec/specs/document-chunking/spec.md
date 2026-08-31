# document-chunking Specification

## Purpose
Turn one functional-spec markdown document into chunks ready to embed,
choosing the split strategy from the shape of each section's content rather
than a fixed size. Implemented by `FunctionalSpecChunker` in
`app/generation/rag/chunking/functional_spec.py`. No embeddings and no
persistence: this capability ends at the chunk list.

## Requirements

### Requirement: Section discovery SHALL be generic across all modules
The 30 modules of the corpus do not share one section layout — headings vary
(`Función` vs `Función general`, `Efecto` vs `Proceso`, `Parámetros de
entrada`, `Información técnica`, ...) and some documents have no H2 structure
at all. Discovery SHALL therefore take EVERY H2 heading as its own section, in
source order, whatever its name. Nothing may be dropped for failing to match a
list of known headings, because a document that silently yields zero chunks is
content lost from the RAG.

Heading text is matched tolerantly: surrounding bold/italic markup is stripped
(`## **_Campos_**` is the section `Campos`).

#### Scenario: Unknown heading name
- **WHEN** a document has an H2 heading that is not one of the five common ones
- **THEN** it becomes a section like any other, keeping its literal heading text

#### Scenario: Prose before the first heading
- **WHEN** real prose sits before the first H2, beyond the title and the id block
- **THEN** it becomes an implicit section labelled `Introducción`

#### Scenario: Document with no H2 headings
- **WHEN** a document carries no H2 heading at all
- **THEN** its whole body is chunked as the implicit `Introducción` section
- **AND** the document does not yield zero chunks

#### Scenario: Placeholder and empty headings
- **WHEN** a heading is a placeholder such as `.`, or its body is empty
- **THEN** that section is dropped

### Requirement: The chunking strategy SHALL follow content shape, not heading name
A section whose body IS a markdown table and nothing else is chunked one row
per chunk; everything else is chunked as narrative. Keying on shape rather than
on the heading name means the same rule serves `Campos`/`Validaciones` and an
equivalent table under any other heading in any module.

#### Scenario: Pure table section
- **WHEN** a section's body is a header row, a separator row, and only table rows
- **THEN** each data row becomes exactly one chunk with `chunk_type` `"table"`

#### Scenario: Narrative section
- **WHEN** a section's body is prose or bullets
- **THEN** it is chunked as narrative with `chunk_type` `"narrative"`

#### Scenario: Table embedded in prose
- **WHEN** a well-formed table sits inside an otherwise narrative section
- **THEN** that table is extracted and chunked one row per chunk
- **AND** the surrounding prose is still chunked as narrative

### Requirement: A table row chunk SHALL be self-contained
A field/rule/error-code row is an atomic fact and SHALL become one chunk, with
its cells labelled by their column headers so the chunk reads without the
original table.

#### Scenario: Row rendered with its headers
- **WHEN** a table row is chunked
- **THEN** its text carries one `header: cell` line per column
- **AND** `metadata.field` holds the row's first cell

### Requirement: Narrative chunking SHALL keep a bullet with its children under a token cap
The unit is the top-level bullet together with all of its nested children — a
child SHALL never be separated from its parent, since a nested condition read
without its parent inverts the business rule. A section small enough stays a
single chunk. A unit over the cap descends one bullet level and repeats.

The token budget for a unit is computed from ITS OWN contextual header, which
grows with the breadcrumb path while descending; a budget estimated once at the
top would let a long breadcrumb silently eat into the cap.

The cap defaults to 500 tokens and is configurable via
`Settings.NARRATIVE_CHUNK_TOKEN_CAP`.

#### Scenario: Section under the cap
- **WHEN** a whole narrative section fits within the cap
- **THEN** it becomes a single chunk and is not subdivided

#### Scenario: Bullet over the cap
- **WHEN** a top-level bullet with its children exceeds the cap
- **THEN** chunking descends to its child bullets and repeats the rule
- **AND** `metadata.bullet_path` records the breadcrumb of labels down to the chunk

#### Scenario: Leaf with no finer structure
- **WHEN** a unit exceeds the cap and has no further bullet level to descend into
- **THEN** it is split on sentence boundaries as a last resort
- **AND** a single run-on clause with no sentence punctuation is split on whole words

### Requirement: Every chunk SHALL carry a contextual header
The embedded text SHALL be prefixed with the document and section context, so a
chunk retrieved on its own still says which transaction and which section it
came from.

#### Scenario: Header format
- **WHEN** any chunk is produced
- **THEN** its `text` begins with `[Documento: {document_id} - {document_title}]`
- **AND** the next line is `[Sección: {section}]`, or
  `[Sección: {section} > {bullet_path}]` when a breadcrumb applies

### Requirement: chunk_id SHALL be traceable and unique within a document
The id format is `{document_id}::{section_slug}::{index}`. The slug is derived
from the Spanish heading text (ASCII-folded, lowercased, underscored) rather
than a hand-maintained translation table, because headings are open-ended
across 30 modules and a fixed dictionary would silently fail on new ones.

#### Scenario: Repeated heading in one document
- **WHEN** a document carries two sections with the same heading text
- **THEN** their chunk indices continue from one counter per slug
- **AND** no two chunks in the document share a `chunk_id`

### Requirement: token_count SHALL be measured with the embedding model's tokenizer
`token_count` SHALL be the token count of the chunk's full `text`, including the
contextual header, measured with `tiktoken` for `text-embedding-3-small`
(`app/generation/rag/chunking/base.py`). No network call and no API key is
involved beyond `tiktoken`'s one-time vocabulary download.

#### Scenario: Count matches the text
- **WHEN** any chunk is produced
- **THEN** `token_count` equals the tokenizer's count of that chunk's `text`

### Requirement: The document id SHALL be extracted tolerantly, per transaction block
A block's own id is written as a standalone line in one of five markup forms
observed in the corpus (`` `**(CODE)**` ``, `` **`(CODE)`** ``, `` `(CODE)` ``,
`` \(`CODE`\) ``, plus one malformed), and codes are NOT always
`[A-Z]{2,4}\d{3}`: real ones include `BC005_k`, `VI7501_A`, `CA13-1` and the
digitless root `MENU`. Reading is therefore two-tiered: the standalone id line
is authoritative and permissive about the code, while the inline fallback
requires digits so that `(CAE)` / `(PAE)` in running prose — variable names in
CA014 — are never mistaken for transaction ids.

The search SHALL be restricted to the head of the block being attributed
(before that block's first H2), not the head of the whole file, so a
multi-transaction document resolves one id per block instead of falling back to
the filename for all of them.

#### Scenario: Id in a block's head
- **WHEN** a block's text before its first H2 carries `` `(CA014)` `` or `` `**(CA001k)**` ``
- **THEN** that block's `document_id` is `CA014` / `CA001k` respectively

#### Scenario: Id form the earlier pattern could not match
- **WHEN** a block declares `` `**(BC005_k)**` ``, `` \(`MENU`\) `` or `` `**(CA13-1)**` ``
- **THEN** the code is recognized rather than falling back to the filename

#### Scenario: Parenthesized prose is not an id
- **WHEN** running prose contains `` \(`CAE`\) `` or `(CA)` mid-sentence
- **THEN** it is not taken as the block's id

#### Scenario: No id found anywhere
- **WHEN** no id block is present in any block of the document
- **THEN** `document_id` falls back to the source filename stem, uppercased

#### Scenario: Document with no H1 heading
- **WHEN** a document has no `# ` heading, as CA014 does not
- **THEN** the whole document is treated as a single block
- **AND** the title falls back to the first non-blank line, emphasis stripped

### Requirement: A block's title SHALL never be its own id line
A block's own title is its H1 heading and nothing else. A block that starts at
its own id line has no title of its own and SHALL fall back to the document's
title, because the alternatives both produce a header that says nothing about
the transaction: taking the id line gave
`[Documento: OP010 - `**(OP010)**`]` (133 documents, 2968 chunks), and taking
the first prose line of the body gave
`[Documento: CA014 - Permite consultar y modificar.]`.

The title reaches the contextual header of every chunk, so it is what a
retrieved chunk uses to say which transaction it belongs to.

#### Scenario: Block starting at its id line
- **WHEN** a block has no H1 of its own, as in a document whose id line is its
  first content
- **THEN** its title is the document's title, e.g. "Coberturas de la póliza
  individual o certificado" for CA014
- **AND** it is never the id block nor a line of body prose

#### Scenario: Block with its own H1
- **WHEN** a block opens with `# Solicitud de código a actualizar`
- **THEN** that heading is its title

### Requirement: A file containing several transactions SHALL attribute each chunk to its own transaction
The file-to-transaction relation is not always one to one: a document can carry
several transactions, each with its own id block — dominantly a transaction plus
its `_k` key-request companion (72 files in the corpus). Chunks SHALL be
attributed per transaction, so a rule documented under one transaction is never
answered under another.

Segmentation SHALL key on the standalone id line, NOT on `# ` (H1): the export
also emits `# ` for bullet continuation lines (`# § _Se construye..._` in
`accounting/cp002.md`), so splitting on H1 invents blocks. Each id line extends
backwards to the nearest preceding H1 — its title — without crossing the
previous id line.

#### Scenario: Two transactions in one file
- **WHEN** chunking a file whose blocks declare `BC005_k` and `BC005`
- **THEN** the chunks of each block carry that block's `document_id`
- **AND** the `_k` entry carries `parent_transaction_code` naming its main
  transaction, set only when that code is declared in the same file

#### Scenario: Bullet continuation lines do not invent blocks
- **WHEN** a document uses `# ` for bullet continuations between its real title
  and a transaction block
- **THEN** only the id-declaring blocks become transactions

#### Scenario: Preamble that names a declared transaction
- **WHEN** the text before the first transaction block resolves to the same code
  as one of the blocks
- **THEN** it is that transaction's own overview and merges into it
- **AND** everything under one `document_id` shares one per-slug chunk counter,
  so no two chunks collide on `chunk_id`

#### Scenario: Preamble that names no declared transaction
- **WHEN** the preamble cannot be attributed to any transaction the file declares
- **THEN** it is kept as a document flagged `is_container`, rather than discarded
  or copied into each child

### Requirement: The authoritative transaction code SHALL come from the document content
The code appears inside the text; the filename SHALL be a fallback only.
Trusting the filename misattributes every multi-transaction file, and the corpus
has filenames carrying a module prefix rather than the bare code
(`accounting_cpl500` documents `CPL500`).

#### Scenario: Filename carries a module prefix
- **WHEN** `accounting_cpl500.md` declares `CPL500` in its content
- **THEN** the `document_id` is `CPL500`, not `ACCOUNTING_CPL500`

#### Scenario: Filename-level fallback picks a declared code
- **WHEN** content with no id of its own must be attributed and the filename stem
  names one of the codes the file declares
- **THEN** that code is used; else the sole declared code; else the stem

### Requirement: An index document SHALL be marked as such without discarding its chunks
A chapter/index document describes a parent node and mostly links to its
children, with no `Campos` or `Validaciones` of its own (`policies/ca001a.md`:
31 links, no table sections). It SHALL be marked `document_kind` `index` and its
chunks SHALL still be produced.

The two errors are not symmetric: marking a real index as content only leaves
some low-value chunks, while marking real content as an index would push
business rules out of the way. Marking instead of dropping leaves the decision
to retrieval and honours the rule of never losing business information silently.

Classification SHALL require BOTH the absence of any pure-table section AND a
high density of links to other documents; either signal alone misfires. The
thresholds are calibrated against the corpus, not derived, so they are settings
(`INDEX_DOC_MIN_LINKS`, `INDEX_DOC_MIN_LINK_DENSITY`).

#### Scenario: Chapter document
- **WHEN** chunking a document with no pure-table section and a high link density
- **THEN** it is reported with `document_kind` `index`
- **AND** its chunks are still produced, each marked `index` in its metadata
- **AND** its links are exposed in `child_links` as parent-child evidence

#### Scenario: Document with a table section, however many links
- **WHEN** a document has a pure-table section and also many links
- **THEN** it is treated as content, because one signal alone is not enough

#### Scenario: Content document with few links
- **WHEN** a document has no table section but few links, or a low density over
  much prose
- **THEN** it is treated as content, not as an index

### Requirement: Chunk metadata SHALL carry the transaction's type and navigation breadcrumb
Retrieval cannot filter by module or transaction type unless the metadata
carries them. The breadcrumb fields SHALL be flat rather than nested, since the
vector store filters by equality, and every one SHALL be optional: the `WINDOWS`
export resolves a path for only part of the corpus (54.2% of documents), and an
unresolved breadcrumb must read as unresolved rather than as a guess.

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

### Requirement: Cross-references SHALL be extracted with a type discriminator
Two reference patterns occur: inline sibling transactions quoted in backticks
(`` `CA003` ``) and footnote-style tags (`<DF009>`). Both SHALL be carried in
ONE list of typed objects rather than two parallel lists. A chunk SHALL NOT
reference its own document.

#### Scenario: Inline transaction reference
- **WHEN** a chunk's text contains a backtick-quoted code such as `` `CAC011` ``
- **THEN** a reference with `type` `"inline_transaction"` is recorded
- **AND** its `context` holds the line the reference appeared in

#### Scenario: Footnote tag reference
- **WHEN** a chunk's text contains a tag such as `<DF009>` or `</DF009>`
- **THEN** a reference with `type` `"footnote_tag"` is recorded

#### Scenario: Self-reference excluded
- **WHEN** the referenced code equals the document's own id
- **THEN** no reference is recorded for it

### Requirement: Overlap and fixed-size splitting SHALL NOT be used as a general strategy
The document's own structure supplies the boundaries. Overlap, fixed-size
windows, and hierarchical or semantic chunking are deliberately absent; the
sentence and word splits exist only as bounded last resorts for a leaf that
cannot be divided structurally.

#### Scenario: No overlap between chunks
- **WHEN** a section is split into several chunks
- **THEN** no text is duplicated across them as deliberate overlap

### Requirement: Un chunk sin información NO DEBE producirse
Un chunk cuyo contenido es estructura markdown sobrante (`###  Proceso`, `#`),
un artefacto del export (`__`), o una fila de tabla con todas sus celdas
vacías, no aporta nada al retrieval y compite con contenido real.

El discriminador es el **contenido, no el largo**. `No aplica.`,
`A petición del usuario.` y `Volver a ejecutar.` son cortos pero son respuestas
reales: con su header contextual dicen "la frecuencia de ejecución de CPL500 es:
a petición del usuario". Descartar por largo habría borrado 291 respuestas
reales junto con el ruido — el mismo error que habría sido filtrar los
encabezados de las tablas rotas en vez de repararlas.

Un heading cuenta como estructura solo cuando su texto es una etiqueta corta: el
export también emite `# ` para líneas de continuación de bullets que sí llevan
contenido (`# § _Se construye el auxiliar concatenando..._`).

#### Scenario: Heading sobrante o artefacto
- **WHEN** el contenido de una unidad es solo un heading con etiqueta corta, o
  solo guiones bajos y puntuación
- **THEN** no se produce chunk

#### Scenario: Fila de tabla con todas sus celdas vacías
- **WHEN** una fila renderizada tiene todos sus valores vacíos
- **THEN** no se produce chunk, porque no hay información que perder

#### Scenario: Contenido corto pero real
- **WHEN** el contenido es una respuesta breve como `No aplica.`
- **THEN** el chunk se produce

#### Scenario: Línea con `#` que lleva contenido
- **WHEN** una línea empieza con `#` pero su texto es una regla y no una etiqueta
- **THEN** el chunk se produce

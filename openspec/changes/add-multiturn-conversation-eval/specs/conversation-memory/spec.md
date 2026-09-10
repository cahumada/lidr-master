# conversation-memory Delta Specification

## ADDED Requirements

### Requirement: The resolver SHALL be measured in both directions

The spec already requires the resolver to be conservative — "with no clear
referent in the facts it returns the question unchanged" — and that property
was the only one measured. Measuring it alone is not neutral: a resolver that
never rewrites satisfies it perfectly, so the number cannot tell a
conservative resolver from a broken one.

Whenever the resolver's behaviour is reported, BOTH rates SHALL be reported
together, over their own denominators:

- the **false positive** rate — questions that name their own subject and
  were rewritten anyway, over the questions that named their own subject;
- the **false negative** rate — questions that depend on the previous turn
  and were left unresolved, over the questions that depended on it.

A rewrite SHALL NOT be reported as correct merely because it happened. The
report SHALL distinguish a rewrite that named the annotated referent from one
that named it alongside an invented one, and from one that named a referent
that was not there — the last being the failure the resolver's own design
calls worse than no rewrite, because it produces a confident search for a
question nobody asked.

#### Scenario: One direction is not a result

- **WHEN** the resolver's behaviour is reported
- **THEN** the false positive and the false negative rate appear together
- **AND** neither is presented as the resolver's accuracy on its own

#### Scenario: A question whose referent is genuinely ambiguous

- **WHEN** a follow-up question admits more than one defensible referent
- **THEN** it is reported apart and counted in neither rate
- **AND** the report says how many such questions the set holds

#### Scenario: The measurement isolates the resolver from retrieval

- **WHEN** the false negative rate is computed
- **THEN** the facts handed to a turn come from the previous turn's annotated
  documents, not from what retrieval returned
- **AND** a miss is attributable to the resolver rather than to retrieval
  having lost the referent first

#### Scenario: The multi-turn golden set is not valid without human review

- **WHEN** the multi-turn golden set has not been reviewed by a person
- **THEN** the file declares it, and the evaluation report repeats it
- **AND** the report says that the annotation deciding each verdict is a human
  judgement about whether a question depends on the previous turn

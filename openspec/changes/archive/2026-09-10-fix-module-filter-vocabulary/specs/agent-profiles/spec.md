# agent-profiles Delta Specification

## MODIFIED Requirements

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

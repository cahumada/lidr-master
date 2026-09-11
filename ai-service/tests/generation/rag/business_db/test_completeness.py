"""`complete` is true when the base declared there was nothing to bring.

|| `complete` es true cuando la base declaró que no había nada que traer.
"""

from __future__ import annotations

import pytest

from app.generation.rag.business_db.models import (
    INCOMPLETE_OUTCOMES,
    RESOLUTION_OUTCOMES,
    BusinessDbContext,
    CodeResolution,
)


def _ctx(*outcomes: str) -> BusinessDbContext:
    resolutions = [
        CodeResolution(code=f"C{index}", outcome=outcome, causes=[outcome])  # type: ignore[arg-type]
        for index, outcome in enumerate(outcomes)
    ]
    return BusinessDbContext(run_id="r", env="PROD", resolutions=resolutions).with_completeness()


@pytest.mark.parametrize(
    "outcome",
    [
        "resolved",
        "not_in_run",
        "no_maintained_table",
        "ng_identi_ignored_by_type",
        "no_validity_mechanism",
        "validity_discrepancy",
    ],
)
def test_declared_absent_is_complete(outcome):
    assert _ctx(outcome).complete is True


@pytest.mark.parametrize("outcome", sorted(INCOMPLETE_OUTCOMES))
def test_each_incompleteness_cause_is_incomplete(outcome):
    assert _ctx(outcome).complete is False


def test_the_vocabulary_is_closed_and_has_no_other():
    assert "otro" not in RESOLUTION_OUTCOMES
    assert "other" not in RESOLUTION_OUTCOMES
    assert set(INCOMPLETE_OUTCOMES).issubset(set(RESOLUTION_OUTCOMES))


def test_a_mixed_list_is_incomplete_if_any_cause_is():
    assert _ctx("no_maintained_table", "table_not_loaded").complete is False


def test_absent_context_is_complete():
    assert BusinessDbContext.absent("no_active_run").complete is True
    assert BusinessDbContext.absent("disabled").complete is True

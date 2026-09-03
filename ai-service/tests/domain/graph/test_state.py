"""Tests for answer-orchestration state reducers.

|| Tests de los reducers del estado de orquestación.
"""

from app.domain.schemas import append_contributions, append_routing


def test_routing_history_is_idempotent_by_step():
    first = append_routing([], [{"step": 0, "next_agent": "query_planner", "reason": "a"}])
    second = append_routing(first, [{"step": 0, "next_agent": "query_planner", "reason": "b"}])
    assert len(second) == 1
    assert second[0]["reason"] == "b"


def test_contributions_merge_by_action_identity():
    first = append_contributions(
        [],
        [{"step": 1, "agent": "evidence_retriever", "action": "tool:search_corpus", "args_digest": "abc"}],
    )
    second = append_contributions(
        first,
        [{"step": 1, "agent": "evidence_retriever", "action": "tool:search_corpus", "args_digest": "abc", "outcome": "ok"}],
    )
    assert len(second) == 1
    assert second[0]["outcome"] == "ok"

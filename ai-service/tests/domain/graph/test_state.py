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


# --- initial_state: donde el defecto de los filtros descartados vivía ---


def _request(**kwargs):
    from app.generation.rag.schemas import AnswerRequest

    return AnswerRequest(question="que valida CA014", **kwargs)


def test_initial_state_seeds_the_request_filters():
    """The defect: these two fields never reached the graph.

    || El defecto: estos dos campos nunca llegaban al grafo.
    """
    from app.domain.graph.runner import initial_state

    state = initial_state(_request(module_code=["CA"], window_type_name=["Menu"]))

    assert state["request_filters"] == {"module_code": ["CA"], "window_type_name": ["Menu"]}


def test_initial_state_does_not_seed_absent_filters():
    """Absent is not an empty list: it means no narrowing was asked for.

    || Ausente no es lista vacía: significa que no se pidió recorte.
    """
    from app.domain.graph.runner import initial_state

    state = initial_state(_request())

    assert state["request_filters"] == {}
    assert "filters" not in state


def test_initial_state_leaves_the_resolution_to_the_planner():
    """`filters` has one author, so the precedence lives in one place.

    || `filters` tiene un solo autor, así la precedencia vive en un solo lugar.
    """
    from app.domain.graph.runner import initial_state

    state = initial_state(_request(module_code=["CA"]))

    assert "filters" not in state
    assert "filter_sources" not in state

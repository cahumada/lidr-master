"""Human review gate tests.

|| Tests del gate de revisión humana.
"""

from app.domain.graph.gate import review_reasons


def test_low_confidence_triggers_review(monkeypatch):
    settings = type(
        "S",
        (),
        {"ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD": 0.6},
    )()
    reasons = review_reasons({"confidence": 0.2, "citations_valid": True}, settings)
    assert any("confidence" in reason for reason in reasons)


def test_clean_state_auto_approves(monkeypatch):
    settings = type(
        "S",
        (),
        {"ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD": 0.6},
    )()
    reasons = review_reasons({"confidence": 0.9, "citations_valid": True}, settings)
    assert reasons == []

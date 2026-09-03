"""Tests for the live activity log and its node-update narration.

|| Tests del log de actividad en vivo y su narración de updates por nodo.
"""

from __future__ import annotations

from app.domain.graph.activity import GraphActivityLog, describe_node
from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE


class TestDescribeNode:
    def test_orchestrator_reports_routing_choice(self):
        update = {
            "next_agent": "evidence_retriever",
            "routing_history": [{"step": 0, "next_agent": "evidence_retriever", "source": "fallback"}],
        }
        [entry] = describe_node("orchestrator", update)
        assert entry["node"] == "orchestrator"
        assert "evidence_retriever" in entry["message"]
        assert "fallback" in entry["message"]

    def test_query_planner_reports_sub_query_count(self):
        update = {"sub_queries": ["a", "b"], "filters": {"module_code": ["CA"]}}
        [entry] = describe_node("query_planner", update)
        assert "2 subconsulta" in entry["message"]
        assert "CA" in entry["message"]

    def test_evidence_retriever_reports_hit_count(self):
        update = {"hits": [{"chunk_id": "1"}, {"chunk_id": "2"}, {"chunk_id": "3"}]}
        [entry] = describe_node("evidence_retriever", update)
        assert "3 chunk" in entry["message"]

    def test_answer_synthesizer_reports_insufficient_context(self):
        update = {"answer": INSUFFICIENT_CONTEXT_MESSAGE, "citations": []}
        [entry] = describe_node("answer_synthesizer", update)
        assert "sin evidencia" in entry["message"]

    def test_answer_synthesizer_reports_answer_length(self):
        update = {"answer": "x" * 42, "citations": [{"chunk_id": "1"}]}
        [entry] = describe_node("answer_synthesizer", update)
        assert "42" in entry["message"]

    def test_citation_validator_reports_grounded(self):
        update = {"citations_valid": True, "confidence": 0.9}
        [entry] = describe_node("citation_validator", update)
        assert "respaldadas" in entry["message"]
        assert "90%" in entry["message"]

    def test_citation_validator_reports_requery(self):
        update = {"citations_valid": False, "requery_requested": True}
        [entry] = describe_node("citation_validator", update)
        assert "requery" in entry["message"] or "nueva evidencia" in entry["message"]

    def test_answer_review_gate_reports_skip(self):
        update = {"needs_human_review": False, "review_reasons": []}
        [entry] = describe_node("answer_review_gate", update)
        assert "lista" in entry["message"]

    def test_answer_review_gate_reports_human_decision(self):
        update = {"human_decision": {"decision": "approve"}}
        [entry] = describe_node("answer_review_gate", update)
        assert "approve" in entry["message"]

    def test_interrupt_reports_reasons(self):
        interrupt = type("I", (), {"value": {"reasons": ["confidence too low"]}})()
        [entry] = describe_node("__interrupt__", (interrupt,))
        assert entry["node"] == "answer_review_gate"
        assert "confidence too low" in entry["message"]
        assert "⏸" in entry["message"]

    def test_unknown_node_degrades_to_generic_line(self):
        [entry] = describe_node("some_future_node", {"whatever": object()})
        assert entry["node"] == "some_future_node"
        assert entry["message"]

    def test_never_raises_on_malformed_update(self):
        # A shape describe_node cannot pattern-match must still return
        # SOMETHING, never propagate — it runs inside a live streaming loop.
        # || Una forma que describe_node no puede reconocer igual tiene que
        # devolver ALGO, nunca propagar — corre dentro de un loop en vivo.
        entries = describe_node("citation_validator", update="not a dict")
        assert entries and entries[0]["message"]


class TestGraphActivityLog:
    def test_unknown_thread_reads_as_none(self):
        log = GraphActivityLog()
        assert log.read("nope") is None

    def test_start_then_append_then_read(self):
        log = GraphActivityLog()
        log.start("t1")
        log.append("t1", "query_planner", "Planificador", "1 subconsulta")
        log.append("t1", "evidence_retriever", "Recuperación", "3 chunks")

        run = log.read("t1")
        assert run.status == "running"
        assert [entry.message for entry in run.entries] == ["1 subconsulta", "3 chunks"]

    def test_finish_sets_terminal_status_and_result(self):
        log = GraphActivityLog()
        log.start("t1")
        log.finish("t1", "completed", result={"answer": "hola"})

        run = log.read("t1")
        assert run.status == "completed"
        assert run.result == {"answer": "hola"}
        assert run.error is None

    def test_finish_records_error_on_failure(self):
        log = GraphActivityLog()
        log.start("t1")
        log.finish("t1", "failed", error="boom")

        run = log.read("t1")
        assert run.status == "failed"
        assert run.error == "boom"

    def test_append_before_start_still_works(self):
        # A defensive default: appending to an unstarted thread should not
        # raise, even though the normal flow always calls start() first.
        # || Un default defensivo: agregar a un hilo sin start() no debería
        # lanzar, aunque el flujo normal siempre llama start() primero.
        log = GraphActivityLog()
        log.append("t1", "orchestrator", "Orquestador", "→ query_planner")
        assert log.read("t1").entries[0].message == "→ query_planner"

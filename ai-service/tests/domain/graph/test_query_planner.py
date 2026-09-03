"""Query planner agent tests.

|| Tests del agente query_planner.
"""

from __future__ import annotations

import asyncio

from app.domain.graph.agents.query_planner import query_planner


def test_decompose_splits_compound_questions():
    state = {
        "query": "En PAC, ¿cómo afecta TRANSBANK, cómo afecta débito automático?",
        "supervisor_steps": 1,
    }
    update = asyncio.run(query_planner(state))
    assert len(update["sub_queries"]) >= 2


def test_transaction_code_suggests_module_filter():
    state = {"query": "¿Qué valida CA014?", "supervisor_steps": 1}
    update = asyncio.run(query_planner(state))
    assert update["filters"].get("module_code") == ["CA"]

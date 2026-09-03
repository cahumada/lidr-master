"""Wire and compile the answer-orchestration graph.

|| Arma y compila el grafo de orquestación de respuestas.
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, START, StateGraph

from app.domain.graph.agents.answer_synthesizer import answer_synthesizer
from app.domain.graph.agents.citation_validator import citation_validator
from app.domain.graph.agents.evidence_retriever import evidence_retriever
from app.domain.graph.agents.query_planner import query_planner
from app.domain.graph.gate import answer_review_gate
from app.domain.graph.orchestrator import orchestrator
from app.domain.schemas import AnswerAgentState

log = structlog.get_logger()

AGENT_NODES = {
    "query_planner": query_planner,
    "evidence_retriever": evidence_retriever,
    "answer_synthesizer": answer_synthesizer,
    "citation_validator": citation_validator,
}


def build_answer_graph(checkpointer=None):
    """Build and compile the answer-orchestration graph.

    || Arma y compila el grafo de orquestación de respuestas.
    """
    builder = StateGraph(AnswerAgentState)

    builder.add_node(
        "orchestrator",
        orchestrator,
        destinations=(*AGENT_NODES, "answer_review_gate"),
    )
    for name, fn in AGENT_NODES.items():
        builder.add_node(name, fn)
    builder.add_node("answer_review_gate", answer_review_gate)

    builder.add_edge(START, "orchestrator")
    for name in AGENT_NODES:
        builder.add_edge(name, "orchestrator")
    builder.add_edge("answer_review_gate", END)

    compiled = builder.compile(checkpointer=checkpointer)
    log.info("answer_graph_built", agents=list(AGENT_NODES))
    return compiled

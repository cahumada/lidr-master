"""Tests that the agent catalog cannot drift from the graph it describes.

|| Tests de que el catálogo de agentes no puede divergir del grafo que describe.
"""

from __future__ import annotations

from app.domain.graph.build import AGENT_NODES, build_answer_graph
from app.domain.graph.catalog import (
    AGENT_KEYS,
    AGENT_SPECS,
    SYNTHESIZER_AGENT,
    agent_spec,
    configurable_agent_keys,
    graph_flow,
)
from app.domain.graph.orchestrator import FALLBACK_LADDER
from app.domain.graph.privilege import AGENT_PRIVILEGES, SEARCH_CORPUS_TOOL


class TestCatalogMatchesTheGraph:
    def test_every_graph_node_is_in_the_catalog(self):
        # The console renders the catalog. A node added to the graph without a
        # spec would be a screen that does not mention an agent that runs.
        # || La consola arma la pantalla con el catálogo. Un nodo agregado al
        # grafo sin spec sería una pantalla que no menciona un agente que corre.
        graph_nodes = set(AGENT_NODES) | {"orchestrator", "answer_review_gate"}

        assert graph_nodes == set(AGENT_KEYS)

    def test_every_catalog_key_has_a_privilege_entry(self):
        # `tools` is derived from the privilege table, so a key missing there
        # would silently report "no tools" instead of failing.
        # || `tools` se deriva de la tabla de privilegios, así que una clave
        # ausente reportaría "sin tools" en silencio en vez de fallar.
        assert set(AGENT_KEYS) <= set(AGENT_PRIVILEGES)

    def test_only_the_retriever_declares_a_tool(self):
        with_tools = {spec.key: spec.tools for spec in AGENT_SPECS if spec.tools}

        assert with_tools == {"evidence_retriever": [SEARCH_CORPUS_TOOL]}


class TestConfigurability:
    def test_only_the_synthesizer_is_llm_driven_today(self):
        llm_driven = {spec.key for spec in AGENT_SPECS if spec.llm_driven}

        assert llm_driven == {SYNTHESIZER_AGENT}

    def test_configurable_agents_are_exactly_the_llm_driven_ones(self):
        # A persona on a deterministic agent would be a setting that does
        # nothing; the API rejects it, and this is where that rule is anchored.
        # || Una persona en un agente determinista sería un setting que no hace
        # nada; la API lo rechaza, y acá se ancla esa regla.
        assert set(configurable_agent_keys()) == {
            spec.key for spec in AGENT_SPECS if spec.llm_driven
        }

    def test_every_spec_says_what_it_is_and_why(self):
        for spec in AGENT_SPECS:
            assert spec.label
            assert spec.role
            assert spec.explanation
            assert spec.kind in {"supervisor", "agent", "gate"}

    def test_an_unknown_key_has_no_spec(self):
        assert agent_spec("no_such_agent") is None


class TestGraphFlowMatchesTheCompiledGraph:
    def test_ladder_is_the_orchestrators_order(self):
        assert graph_flow()["ladder"] == list(FALLBACK_LADDER)

    def test_nodes_cover_exactly_the_catalog(self):
        assert {node["key"] for node in graph_flow()["nodes"]} == set(AGENT_KEYS)

    def test_edges_match_the_compiled_graph(self):
        compiled = build_answer_graph()
        served = {(edge["source"], edge["target"]) for edge in graph_flow()["edges"]}
        compiled_edges = set()
        for edge in compiled.get_graph().edges:
            source = "START" if edge.source in {"__start__", "START"} else edge.source
            target = "END" if edge.target in {"__end__", "END"} else edge.target
            compiled_edges.add((source, target))

        assert served == compiled_edges

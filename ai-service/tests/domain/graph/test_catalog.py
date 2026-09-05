"""Tests that the agent catalog cannot drift from the graph it describes.

|| Tests de que el catálogo de agentes no puede divergir del grafo que describe.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.graph.agents.query_planner import _suggest_filters
from app.domain.graph.build import AGENT_NODES, build_answer_graph
from app.domain.graph.catalog import (
    AGENT_KEYS,
    AGENT_SPECS,
    EXAMPLE_NOTE,
    EXAMPLE_QUESTION,
    EXAMPLE_SOURCE,
    EXAMPLE_SUB_QUERIES,
    SYNTHESIZER_AGENT,
    agent_spec,
    configurable_agent_keys,
    graph_flow,
    tool_catalog,
)
from app.domain.graph.orchestrator import FALLBACK_LADDER
from app.domain.graph.privilege import AGENT_PRIVILEGES, SEARCH_CORPUS_TOOL
from app.generation.rag.retrieval.decomposition import decompose

GOLDEN_CURATED = Path(__file__).resolve().parents[3] / "evals" / "golden_curated.json"
EXAMPLE_GOLDEN_ID = "U-multi-lote-pac-rechazos"


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

    def test_only_the_retriever_uses_a_tool(self):
        used = {spec.key: list(spec.tools_used) for spec in AGENT_SPECS if spec.tools_used}

        assert used == {"evidence_retriever": [SEARCH_CORPUS_TOOL]}
        assert agent_spec(SYNTHESIZER_AGENT).tools_used == ()

    def test_the_tool_catalog_covers_every_granted_name(self):
        catalog = tool_catalog()
        names = {item["name"] for item in catalog}

        assert names == {SEARCH_CORPUS_TOOL}
        search = next(item for item in catalog if item["name"] == SEARCH_CORPUS_TOOL)
        assert search["granted_to"] == ["evidence_retriever"]
        assert search["used_by"] == ["evidence_retriever"]
        assert search["description"]


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


class TestTheWorkedExampleCannotDrift:
    """The example is prose on a screen, so it reads as a fact. These tests are
    what make the deterministic half of it one.

    || El ejemplo es prosa en una pantalla, así que se lee como un hecho. Estos
    tests son lo que hace que la mitad determinista lo sea.
    """

    def test_every_node_says_what_it_receives_and_leaves(self):
        # A node without an example is a card the flow screen cannot explain,
        # which is the whole problem this example exists to fix.
        # || Un nodo sin ejemplo es una ficha que la pantalla no puede explicar.
        for spec in AGENT_SPECS:
            assert spec.example.receives
            assert spec.example.leaves

    def test_the_planner_example_is_what_decompose_returns(self):
        # Written out in the catalog so the console can show them verbatim; if
        # `decompose()` changes, this fails instead of the screen quietly
        # showing a split the code no longer produces.
        # || Escritas en el catálogo para mostrarlas tal cual; si `decompose()`
        # cambia, falla acá y no en silencio en la pantalla.
        assert list(EXAMPLE_SUB_QUERIES) == decompose(EXAMPLE_QUESTION)

    def test_the_planner_example_claims_no_filters(self):
        # The example text says the heuristic proposes no `module_code` for
        # this question. That claim is only true while the heuristic agrees.
        # || El texto del ejemplo dice que la heurística no propone
        # `module_code`; solo es cierto mientras la heurística coincida.
        assert _suggest_filters(EXAMPLE_QUESTION) == {}

    def test_the_example_question_is_the_annotated_golden_one(self):
        # Its value is that a person asked it and a person annotated it. A
        # question edited here and not there would lose exactly that.
        # || Su valor es que la preguntó una persona y la anotó una persona.
        entries = json.loads(GOLDEN_CURATED.read_text(encoding="utf-8"))["questions"]
        golden = next(entry for entry in entries if entry["id"] == EXAMPLE_GOLDEN_ID)

        assert EXAMPLE_QUESTION == golden["question"]
        assert EXAMPLE_GOLDEN_ID in EXAMPLE_SOURCE

    def test_the_retriever_example_cites_the_annotated_documents(self):
        # The documents shown are the annotated ones, not a recorded run — the
        # screen says so, and this keeps the two lists the same.
        # || Los documentos mostrados son los anotados, no una corrida grabada.
        entries = json.loads(GOLDEN_CURATED.read_text(encoding="utf-8"))["questions"]
        golden = next(entry for entry in entries if entry["id"] == EXAMPLE_GOLDEN_ID)
        shown = [line.split(" ", 1)[0] for line in agent_spec("evidence_retriever").example.detail]

        assert shown == golden["relevant_document_ids"]

    def test_illustrative_examples_are_marked(self):
        # The synthesizer writes with a model and the retriever depends on the
        # loaded corpus. Both must carry a caveat; the deterministic nodes must
        # not, or the mark would stop meaning anything.
        # || El sintetizador escribe con un modelo y el recuperador depende del
        # corpus. Los dos llevan salvedad; los deterministas no, o la marca
        # dejaría de significar algo.
        with_caveat = {spec.key for spec in AGENT_SPECS if spec.example.caveat}

        assert with_caveat == {"answer_synthesizer", "evidence_retriever"}

    def test_flow_serves_the_example(self):
        flow = graph_flow()

        assert flow["example"] == {
            "question": EXAMPLE_QUESTION,
            "source": EXAMPLE_SOURCE,
            "note": EXAMPLE_NOTE,
        }
        for node in flow["nodes"]:
            assert node["example"]["receives"]
            assert node["example"]["leaves"]

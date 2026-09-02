"""Tests for the process map.

The map will be used to answer *"what do I have to run first"*, so most of
these are about NOT producing an edge: a `Requisitos` section that talks about
permissions, a code that no document owns, an index document's table of
contents. Every input is a real one from the corpus.

|| Tests del mapa de procesos. El mapa se va a usar para responder *"qué tengo
que correr antes"*, así que la mayoría de estos son sobre NO producir una
arista: una sección `Requisitos` que habla de permisos, un código que ningún
documento tiene, la tabla de contenidos de un índice. Cada entrada es una real
del corpus.
"""

from __future__ import annotations

import pytest

from app.generation.rag.navigation import NavigationTree
from app.generation.rag.process_map.builder import build, to_json
from app.generation.rag.process_map.cag import (
    ContextTooLargeError,
    render,
    render_limits,
)
from app.generation.rag.process_map.graph import Edge, ProcessMap, detect_cycles
from app.generation.rag.process_map.requisites import (
    declares_precedence,
    extract_codes,
    extract_precedence,
    section_text,
)


def chunk(text: str, *, section: str = "Requisitos", chunk_type: str = "narrative") -> dict:
    return {
        "chunk_id": f"X::{section}::1",
        "text": f"[Documento: X - T]\n[Sección: {section}]\n{text}",
        "token_count": 10,
        "metadata": {"section": section, "chunk_type": chunk_type},
    }


def document(code: str, chunks: list[dict], **extra) -> dict:
    return {"document_id": code, "document_title": f"Título de {code}", "chunks": chunks, **extra}


# --- Does this section declare precedence? ----------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Este proceso requiere que previamente se ejecute uno o varios de los siguientes procesos:",
        "Previamente se debe ejecutar la interfaz que alimenta la tabla temporal.",
        "Se deben ejecutar antes los procesos de:",
        "Antes de la ejecución de este proceso se deben ejecutar los siguiemtes otros:",
        "Antes de ejecutar este programa, el usuario debe ejecutar el proceso.",
    ],
)
def test_real_precedence_lead_ins_are_recognised(text):
    """All five are verbatim from the corpus, typo included: `CRL663` writes
    "siguiemtes". Matching the lead-in verb phrase rather than the list phrase
    is what survives that."""
    assert declares_precedence(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "No aplica.",
        "Se recomienda que sea un proceso nocturno.",
        "El usuario debe tener permisos sobre el módulo de cobranzas.",
        "Se requiere que la tabla de parámetros esté cargada.",
        "",
    ],
)
def test_requirements_of_another_kind_declare_no_precedence(text):
    """122 of 228 `Requisitos` sections say `No aplica.` and 105 are
    requirements of another kind. Treating those as precedence would fill the
    map with edges nobody declared."""
    assert declares_precedence(text) is False


# --- Which codes come out ----------------------------------------------------


def test_linked_codes_are_extracted():
    text = "[COL500](col500.html) | [Generación de cobranzas](col500.html)"
    assert extract_codes(text, exclude="COL502", known={"COL500"}) == ("COL500",)


def test_bare_codes_are_extracted():
    """`COL520` writes its dependencies as plain text with no link at all, and
    skipping those cost 24 of the 39 edges."""
    text = "Código: COL500 Descripción: Generación de cobranzas Código: CO501"
    assert extract_codes(text, exclude="COL520", known={"COL500", "CO501"}) == ("CO501", "COL500")


def test_a_code_no_document_owns_is_dropped():
    """An edge pointing at nothing would make the map look more connected than
    it is."""
    text = "requiere [ZZ999](zz999.html)"
    assert extract_codes(text, exclude="X", known={"COL500"}) == ()


def test_a_document_does_not_require_itself():
    text = "[COL502](col502.html) y [COL500](col500.html)"
    assert extract_codes(text, exclude="COL502", known={"COL502", "COL500"}) == ("COL500",)


# --- The section, not the chunk -----------------------------------------------


def test_the_lead_in_and_its_codes_can_live_in_different_chunks():
    """The `Requisitos` section of `COL502` becomes four chunks: three table
    rows with the codes and one narrative with the lead-in. Chunk by chunk the
    two never meet, which is why extraction reads the whole section -- 9 edges
    per chunk, 39 per section."""
    chunks = [
        chunk("Código: [COL500](col500.html)\nDescripción: Generación", chunk_type="table"),
        chunk("Código: [CO501](co501.html)\nDescripción: Rechazos", chunk_type="table"),
        chunk("Este proceso requiere que previamente se ejecute uno o varios de los siguientes:"),
    ]

    precedence = extract_precedence("COL502", chunks, known_documents={"COL500", "CO501"})

    assert precedence is not None
    assert precedence.requires == ("CO501", "COL500")


def test_the_header_does_not_contribute_codes():
    """Every chunk's header repeats the document title, and a title carrying a
    code would become a dependency on itself or on whatever it names."""
    chunks = [chunk("requiere que previamente se ejecute [COL500](col500.html)")]
    text = section_text(chunks)
    assert "[Documento:" not in text


def test_precedence_without_a_nameable_target_is_recorded_not_dropped():
    """`SIL500` declares "previamente se debe ejecutar la interfaz que alimenta
    la tabla temporal": a real dependency whose target cannot be resolved.
    Dropping it would hide a declaration the document made."""
    chunks = [chunk("Previamente se debe ejecutar la interfaz que alimenta la tabla temporal.")]

    precedence = extract_precedence("SIL500", chunks, known_documents={"COL500"})

    assert precedence is not None
    assert precedence.unresolved is True
    assert precedence.requires == ()
    assert "interfaz" in precedence.evidence


def test_a_section_that_declares_nothing_yields_no_precedence():
    assert extract_precedence("COL821", [chunk("No aplica.")], known_documents={"X"}) is None


def test_no_requisitos_section_yields_no_precedence():
    assert extract_precedence("X", [], known_documents={"X"}) is None


def test_the_evidence_points_back_to_the_sentence():
    """Any edge has to be auditable back to the sentence that produced it."""
    chunks = [chunk("Este proceso requiere que previamente se ejecute [COL500](col500.html).")]
    precedence = extract_precedence("COL502", chunks, known_documents={"COL500"})
    assert "requiere que previamente" in precedence.evidence


# --- The graph ----------------------------------------------------------------


def tree_of(rows: list[tuple[str, str | None, str]]) -> NavigationTree:
    return NavigationTree(rows)


def test_the_hierarchy_becomes_menu_parent_edges():
    tree = tree_of([("MENU", None, "Raíz"), ("DMECAR", "MENU", "Cartera"),
                    ("CA014", "DMECAR", "Datos de póliza")])
    process_map = build({"CA014": document("CA014", [chunk("x", section="Función")])}, tree)

    edges = {(e.source, e.target) for e in process_map.edges_of("menu_parent")}
    assert ("CA014", "DMECAR") in edges
    assert ("DMECAR", "MENU") in edges


def test_a_leaf_with_no_parent_is_marked_unreachable():
    """714 transactions exist as a window and hang off no menu. That is how the
    system is, so it goes IN the map rather than being dropped."""
    tree = tree_of([
        ("MENU", None, "Raíz"),
        ("DMECAR", "MENU", "Cartera"),          # sí cuelga del menú
        ("CPL011", None, "Asientos automáticos"),  # no cuelga de nada
    ])
    process_map = build({}, tree)

    assert process_map.nodes["CPL011"].unreachable_from_menu is True
    assert process_map.nodes["DMECAR"].unreachable_from_menu is False
    assert process_map.coverage.unreachable_from_menu == 1


def test_the_root_itself_is_not_called_unreachable():
    """The root has no parent by definition; calling it unreachable would be a
    miscount."""
    tree = tree_of([("MENU", None, "Raíz"), ("DMECAR", "MENU", "Cartera")])
    assert build({}, tree).nodes["MENU"].unreachable_from_menu is False


def test_a_whole_subtree_hanging_off_nothing_is_unreachable():
    """3 codes have no parent but do have children, and every descendant of
    those is as unreachable from the menu as they are. Marking only the
    parentless node would undercount."""
    tree = tree_of([
        ("MENU", None, "Raíz"),
        ("HUERFANO", None, "Subárbol colgado de la nada"),
        ("HIJO", "HUERFANO", "Hijo del huérfano"),
    ])
    process_map = build({}, tree)

    assert process_map.nodes["HUERFANO"].unreachable_from_menu is True
    assert process_map.nodes["HIJO"].unreachable_from_menu is True


def test_the_three_relations_never_mix():
    tree = tree_of([("MENU", None, "R"), ("CA014", "MENU", "Póliza")])
    documents = {
        "CA014": document("CA014", [chunk("ver [CA001](ca001.html)", section="Notas")]),
        "CA001": document("CA001", [chunk("x", section="Función")]),
        "COL502": document(
            "COL502",
            [chunk("requiere que previamente se ejecute [CA001](ca001.html)")],
        ),
    }
    process_map = build(documents, tree)

    assert {e.source for e in process_map.edges_of("requires")} == {"COL502"}
    assert ("CA014", "CA001") in {(e.source, e.target) for e in process_map.edges_of("references")}
    assert all(e.edge_type == "menu_parent" for e in process_map.edges_of("menu_parent"))


def test_an_index_documents_links_are_marked_as_such():
    """The biggest emitters of `references` are index documents -- `LIFE_INDEX`
    with 130. A consumer that read those as precedence would conclude that
    index has 130 process dependencies."""
    documents = {
        "LIFE_INDEX": document(
            "LIFE_INDEX",
            [chunk("[VI001](vi001.html)", section="Páginas")],
            document_kind="index",
        ),
        "VI001": document("VI001", [chunk("x", section="Función")]),
    }
    process_map = build(documents, None)

    edge = process_map.edges_of("references")[0]
    assert edge.origin == "index_document"


def test_every_edge_carries_its_type_and_origin():
    tree = tree_of([("MENU", None, "R"), ("CA014", "MENU", "P")])
    for edge in build({"CA014": document("CA014", [chunk("x", section="F")])}, tree).edges:
        assert edge.edge_type
        assert edge.origin


def test_a_reference_to_a_document_that_does_not_exist_is_dropped():
    documents = {"CA014": document("CA014", [chunk("ver [ZZ999](zz999.html)", section="Notas")])}
    assert build(documents, None).edges_of("references") == []


# --- Cycles --------------------------------------------------------------------


def test_a_cycle_is_detected_and_does_not_hang():
    """The window-tree export contains two, so a naive walk would hang the run."""
    edges = [
        Edge("A", "B", "menu_parent", "windows_tree"),
        Edge("B", "C", "menu_parent", "windows_tree"),
        Edge("C", "A", "menu_parent", "windows_tree"),
    ]
    assert detect_cycles(edges, "menu_parent")


def test_an_acyclic_graph_reports_no_cycles():
    edges = [
        Edge("A", "B", "menu_parent", "windows_tree"),
        Edge("B", "C", "menu_parent", "windows_tree"),
    ]
    assert detect_cycles(edges, "menu_parent") == []


def test_cycles_of_one_relation_do_not_count_for_another():
    edges = [
        Edge("A", "B", "references", "chunk_reference"),
        Edge("B", "A", "references", "chunk_reference"),
    ]
    assert detect_cycles(edges, "menu_parent") == []
    assert detect_cycles(edges, "references")


# --- Coverage ------------------------------------------------------------------


def test_coverage_counts_what_is_not_covered():
    tree = tree_of([("MENU", None, "R"), ("MA9999", "MENU", "Ventana sin documento")])
    documents = {"INSCALX": document("INSCALX", [chunk("x", section="Proceso")])}
    coverage = build(documents, tree).coverage

    assert coverage.window_codes_without_document == 2  # MENU y MA9999
    assert coverage.documents_that_are_not_windows == 1  # INSCALX


def test_the_artifact_carries_coverage_nodes_and_edges():
    tree = tree_of([("MENU", None, "R"), ("CA014", "MENU", "P")])
    artifact = to_json(build({"CA014": document("CA014", [chunk("x", section="F")])}, tree))

    assert set(artifact) == {"coverage", "unresolved_precedence", "nodes", "edges"}
    assert artifact["coverage"]["nodes"] == 2


# --- The CAG context ------------------------------------------------------------


def test_the_context_declares_its_own_limits():
    """A model that gets the map without its limits will answer that a
    transaction does not exist when what happens is it is not in the menu."""
    tree = tree_of([("MENU", None, "R"), ("CPL011", None, "Asientos")])
    limits = render_limits(build({}, tree))

    assert "no cuelgan de ningún menú" in limits
    assert "NO significa que no exista" in limits
    assert "No inventar relaciones" in limits


def test_the_context_says_the_three_relations_mean_different_things():
    limits = render_limits(ProcessMap())
    assert "`requires`" in limits
    assert "`references`" in limits
    assert "NO implica dependencia" in limits


def test_the_context_is_measured_with_the_models_tokenizer():
    tree = tree_of([("MENU", None, "R"), ("CA014", "MENU", "P")])
    _, tokens = render(build({}, tree), max_tokens=100_000)
    assert tokens > 0


def test_over_the_ceiling_it_fails_instead_of_truncating():
    """Half a map reads as a whole one, which is worse than not having it."""
    tree = tree_of([("MENU", None, "R"), ("CA014", "MENU", "P")])
    process_map = build({}, tree)

    with pytest.raises(ContextTooLargeError, match="over the"):
        render(process_map, max_tokens=10)


def test_the_failure_says_what_to_drop_first():
    with pytest.raises(ContextTooLargeError) as error:
        render(build({}, tree_of([("MENU", None, "R")])), max_tokens=1)
    message = str(error.value)
    assert "Nothing was written" in message
    assert "hierarchy" in message and "precedence" in message

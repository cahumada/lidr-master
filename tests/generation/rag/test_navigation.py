"""Tests for the WINDOWS navigation tree: breadcrumb resolution at variable
depth, the structural node/leaf rule, and honest handling of what the export
does not cover. Uses the real export in data/windows_tree.csv."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.generation.rag.chunking.functional_spec import FunctionalSpecChunker
from app.generation.rag.navigation import (
    NavigationTree,
    get_navigation_tree,
    load_navigation_tree,
)
from app.generation.rag.taxonomy import classify_transaction_type

REPO_ROOT = Path(__file__).resolve().parents[3]
TREE_PATH = REPO_ROOT / "data" / "windows_tree.csv"
DATA_ROOT = REPO_ROOT / "data"


@pytest.fixture(scope="module")
def tree() -> NavigationTree:
    loaded = get_navigation_tree(TREE_PATH)
    assert loaded is not None, f"expected the WINDOWS export at {TREE_PATH}"
    return loaded


# --- The two cases validated in the domain note -----------------------------


def test_ca001_resolves_a_module_with_no_submodule(tree):
    """Domain note: MENU -> DMECAR ('Pólizas') -> CA001, no intermediate level."""
    location = tree.locate("CA001")

    assert location.module_code == "DMECAR"
    assert "lizas" in (location.module_name or ""), location.module_name
    assert location.submodule_code is None, "CA001 has no submodule; it must not be invented"
    assert location.navigation_path == "MENU > DMECAR > CA001"
    assert location.is_menu_node is False


def test_cac020_resolves_a_module_and_a_submodule(tree):
    """Domain note: MENU -> DMECAR -> DMECCA ('Consultas de Pólizas') -> CAC020."""
    location = tree.locate("CAC020")

    assert location.module_code == "DMECAR"
    assert location.submodule_code == "DMECCA"
    assert "Consultas" in (location.submodule_name or "")
    assert location.navigation_path == "MENU > DMECAR > DMECCA > CAC020"
    assert location.is_menu_node is False


def test_depth_beyond_the_two_documented_cases_is_supported(tree):
    """The real export runs to 6 levels. The submodule is the first level under
    the module, and the full path is kept so nothing deeper is lost."""
    location = tree.locate("MA0001")

    assert location.module_code == "DMEMAN"
    assert location.submodule_code == "MTCAR"
    assert location.navigation_path == "MENU > DMEMAN > MTCAR > MPRCO2 > MA0001"


# --- The structural node/leaf rule ------------------------------------------


@pytest.mark.parametrize("code", ["MCONTA", "MERCP", "MCAJBA", "MGENER"])
def test_codes_the_domain_note_calls_folders_are_nodes(code, tree):
    assert tree.locate(code).is_menu_node is True


@pytest.mark.parametrize("code", ["MCO511"])
def test_codes_the_domain_note_calls_leaves_are_leaves(code, tree):
    """MEGAA used to be in this list and is deliberately out of it now: the
    domain note called it a leaf because nothing hangs off it, but the export
    DECLARES it window type 8, "Menu". A declaration beats an inference drawn
    from absence. See test_an_empty_menu_is_still_a_menu."""
    assert tree.locate(code).is_menu_node is False


def test_ma6835_is_not_a_folder_it_is_a_self_loop(tree):
    """This test used to assert MA6835 was a menu folder, on the strength of the
    has-children heuristic. It is not: the row is its OWN parent -- a self-loop,
    and one of the two cycles the process map detects -- so the only "child" it
    has is itself. Its declared window type is 10, "Tabla general".

    The domain note recorded the artifact as a domain fact, which is exactly
    what an authoritative field is for."""
    assert classify_transaction_type("MA6835").transaction_type == "maintenance"
    assert tree.parent_of("MA6835") == "MA6835", "the self-loop is the whole point"
    assert tree.has_children("MA6835") is False
    assert tree.window_type_name("MA6835") == "Tabla general"
    assert tree.locate("MA6835").is_menu_node is False
    assert (
        classify_transaction_type("MA6835", is_menu_node=True).transaction_type == "menu_node"
    )


def test_a_leaf_keeps_its_pattern_type(tree):
    location = tree.locate("MA0001")
    assert (
        classify_transaction_type("MA0001", is_menu_node=location.is_menu_node).transaction_type
        == "maintenance"
    )


# --- What the export does NOT cover -----------------------------------------


def test_a_code_absent_from_the_tree_resolves_nothing(tree):
    location = tree.locate("NO_EXISTE_ESTE_CODIGO")

    assert location.module_code is None
    assert location.navigation_path is None
    assert location.is_menu_node is None, "absent must read as absent, not as a leaf"


def test_a_code_whose_chain_never_reaches_the_root_claims_no_breadcrumb(tree):
    """324 codes sit under a parent that leads nowhere. Calling their first
    ancestor a 'module' would invent a taxonomy."""
    location = tree.locate("AG001")

    assert location.module_code is None
    assert location.navigation_path is None
    # It is still in the tree, so the node/leaf fact is known.
    assert location.is_menu_node is not None


def test_traversal_survives_the_cycles_in_the_export(tree):
    """The export contains 2 cycles; a naive walk would hang the batch run."""
    for code in ("CA001", "MA0001", "MA6835", "AG001"):
        assert len(tree.path(code)) < 50


# --- Optionality: the export is not a precondition --------------------------


def test_a_missing_export_is_not_an_error(tmp_path):
    assert load_navigation_tree(tmp_path / "no_such_file.csv") is None


def test_the_chunker_works_without_a_tree():
    """Without the export the pipeline behaves as before and resolves no
    breadcrumb, rather than failing."""
    content = (DATA_ROOT / "policies" / "ca014.md").read_text(encoding="utf-8")
    documents = FunctionalSpecChunker(navigation_tree=None).chunk("ca014.md", content)

    assert documents[0].chunks
    assert documents[0].navigation_path is None
    assert documents[0].is_menu_node is None
    assert all(c.metadata.module_code is None for c in documents[0].chunks)


def test_the_breadcrumb_reaches_the_chunk_metadata(tree):
    content = (DATA_ROOT / "policies" / "ca001.md").read_text(encoding="utf-8")
    documents = FunctionalSpecChunker(navigation_tree=tree).chunk("ca001.md", content)

    # ca001.md declares CA001k, whose own code is not in the tree; the point
    # here is that whatever resolves is propagated to every chunk.
    document = documents[0]
    for chunk in document.chunks:
        assert chunk.metadata.module_code == document.chunks[0].metadata.module_code


def test_an_empty_menu_is_still_a_menu(tree):
    """16 codes are declared window type 8 with nothing hanging off them. The
    has-children heuristic called them executable transactions; the export says
    they are folders. An empty folder is still a folder, and
    `classify_transaction_type` reads this, so the 16 were propagating."""
    assert tree.window_type_name("MEGAA") == "Menu"
    assert tree.has_children("MEGAA") is False
    assert tree.is_menu_node("MEGAA") is True


def test_the_declared_type_only_yields_to_the_heuristic_when_absent(tree):
    """Two of the 3389 rows carry no window type. For those, and for anything the
    export does not list at all, the heuristic is still the answer."""
    without_type = [code for code in tree.codes() if tree.window_type(code) is None]
    assert without_type, "the export has rows with no declared type"
    for code in without_type:
        assert tree.is_menu_node(code) == tree.has_children(code)


def test_the_window_type_travels_by_name_not_by_code(tree):
    """`6` tells nobody anything; the chunk gets embedded for a model to read."""
    assert tree.window_type_name("MENU") == "Menu"
    assert tree.window_type_name("NO_EXISTE") is None

"""Window status stamping on functional-spec chunks."""

from __future__ import annotations

from pathlib import Path

from app.generation.rag.chunking.functional_spec import FunctionalSpecChunker
from app.generation.rag.navigation import NavigationTree

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT / "data"


def test_a_resolved_status_is_stamped_on_every_chunk():
    tree = NavigationTree([("CA014", "MENU", "Pólizas", "1", "", "3")])
    content = (DATA_ROOT / "policies" / "ca014.md").read_text(encoding="utf-8")
    documents = FunctionalSpecChunker(navigation_tree=tree).chunk("ca014.md", content)

    assert documents[0].document_id == "CA014"
    assert all(chunk.metadata.window_status == "Acceso restringido" for chunk in documents[0].chunks)


def test_without_a_tree_status_stays_absent():
    content = (DATA_ROOT / "policies" / "ca014.md").read_text(encoding="utf-8")
    documents = FunctionalSpecChunker(navigation_tree=None).chunk("ca014.md", content)

    assert all(chunk.metadata.window_status is None for chunk in documents[0].chunks)

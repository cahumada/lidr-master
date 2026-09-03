"""Output guardrail: a cited document_id must be in the retrieved hits.

Input is not tested here on purpose: it is ``Field(min_length=2)`` on
``AnswerRequest``, the same rule ``/search`` already enforces.

|| Guardrail de salida: un document_id citado tiene que estar en los hits
recuperados. La entrada no se testea acá a propósito: es
``Field(min_length=2)`` en ``AnswerRequest``, la misma regla que ya impone
``/search``.
"""

from __future__ import annotations

from app.generation.rag.guardrails import (
    check_grounding,
    citations_cover_expected,
    extract_cited_document_ids,
)
from app.generation.rag.schemas import SearchHit


def _hit(document_id: str, section: str = "Validaciones") -> SearchHit:
    return SearchHit(
        content_hash=f"h-{document_id}",
        chunk_id=f"{document_id}::{section}::0",
        document_id=document_id,
        document_title=None,
        section=section,
        bullet_path=None,
        module_code=None,
        document_kind="content",
        text="texto",
        score=0.1,
        branches=["vector"],
        ranks={"vector": 1},
    )


def test_a_citation_of_a_retrieved_document_is_grounded():
    result = check_grounding(
        "El capital no puede superar el máximo. [CA014 · Validaciones]",
        [_hit("CA014")],
    )

    assert result.grounded is True
    assert result.cited_document_ids == ["CA014"]
    assert result.unsupported_document_ids == []


def test_an_invented_document_id_is_not_grounded():
    result = check_grounding(
        "Según [ZZ999 · Función] el campo es obligatorio.",
        [_hit("CA014")],
    )

    assert result.grounded is False
    assert result.unsupported_document_ids == ["ZZ999"]


def test_citations_are_the_hits_not_what_the_model_claimed():
    """The guardrail never puts an invented id into the caller's citations.
    That list is built from hits, elsewhere; this only marks the prose."""
    hits = [_hit("CA014")]
    result = check_grounding("Mira [ZZ999 · Función].", hits)

    assert result.grounded is False
    assert [hit.document_id for hit in hits] == ["CA014"]


def test_no_markers_means_nothing_was_invented():
    result = check_grounding(
        "No hay información suficiente en la documentación recuperada para responder.",
        [_hit("CA014")],
    )

    assert result.grounded is True
    assert result.cited_document_ids == []


def test_a_repeated_citation_is_counted_once():
    assert extract_cited_document_ids(
        "[CA014 · Validaciones] y otra vez [CA014 · Función]"
    ) == ["CA014"]


def test_drifted_separators_still_count_as_citations():
    """Models replace the middle dot. A real document cited with a pipe is
    still grounded; a fake one with a dash is still unsupported."""
    grounded = check_grounding("[CA014 | Validaciones]", [_hit("CA014")])
    fake = check_grounding("[ZZ999 - Función]", [_hit("CA014")])

    assert grounded.grounded is True
    assert fake.unsupported_document_ids == ["ZZ999"]


def test_matching_is_case_insensitive():
    result = check_grounding("[ca014 · Validaciones]", [_hit("CA014")])
    assert result.grounded is True


def test_fidelity_is_coverage_of_an_expected_id():
    """The eval's predicate: at least one annotated document in citations."""
    assert citations_cover_expected(["CA014", "COL005"], {"COL005"}) is True
    assert citations_cover_expected(["CA014"], {"COL005"}) is False
    assert citations_cover_expected(["ca014"], {"CA014"}) is True

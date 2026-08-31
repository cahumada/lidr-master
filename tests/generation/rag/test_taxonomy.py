"""Tests for transaction type classification and index-document detection.
Codes are real ones taken from the corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.generation.rag.chunking.functional_spec import (
    FunctionalSpecChunker,
    classify_document_kind,
    extract_child_links,
    parse_sections,
)
from app.generation.rag.taxonomy import classify_transaction_type

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


def _read(relative: str) -> str:
    return (DATA_ROOT / relative).read_text(encoding="utf-8")


# --- Group 4: type classification -------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # interface — from the Interfaces module generator
        ("INT54050", "interface"),
        ("INT54584", "interface"),
        # key request — the `_k` companion, plus the single bare-`k` case
        ("BC005_k", "key_request"),
        ("SG001_K", "key_request"),
        ("CPL999_k", "key_request"),
        ("CA001k", "key_request"),
        # process / report — [Módulo]L[código]
        ("CAL013", "process_report"),
        ("CPL500", "process_report"),
        ("VIL009", "process_report"),
        # query — [Módulo]C[código]
        ("CAC020", "query"),
        ("CRC001", "query"),
        ("AUC001", "query"),
        # maintenance — M[Módulo][código]
        ("MA0001", "maintenance"),
        ("MCO511", "maintenance"),
        # functional / ABM — neither L nor C
        ("CA001", "functional_abm"),
        ("CA014", "functional_abm"),
        ("CO001", "functional_abm"),
    ],
)
def test_classify_real_codes(code, expected):
    assert classify_transaction_type(code).transaction_type == expected


@pytest.mark.parametrize(
    "code",
    [
        "ACCOUNTING_INDEX",  # a filename fallback, not a transaction code
        "VALSCHEMA",
        "TR_CAP_ANNUAL",
        "MENU",  # the tree root: a menu node, not an executable transaction
        "",
    ],
)
def test_unrecognized_codes_are_unknown_with_a_reason(code):
    """An invented default type would propagate as if it were evidence."""
    result = classify_transaction_type(code)
    assert result.transaction_type == "unknown"
    assert result.reason, "an unknown classification must say why"


def test_a_classified_code_carries_no_reason():
    assert classify_transaction_type("CA014").reason is None


def test_specific_patterns_win_over_the_generic_one():
    """MA0001, AGL001, AGC001 and INT54050 all also match the generic
    functional_abm shape; rule order is what keeps them apart."""
    assert classify_transaction_type("MA0001").transaction_type == "maintenance"
    assert classify_transaction_type("AGL001").transaction_type == "process_report"
    assert classify_transaction_type("AGC001").transaction_type == "query"
    assert classify_transaction_type("INT54050").transaction_type == "interface"


def test_the_type_reaches_the_chunk_metadata():
    documents = FunctionalSpecChunker().chunk("ca014.md", _read("policies/ca014.md"))

    assert documents[0].transaction_type == "functional_abm"
    assert all(c.metadata.transaction_type == "functional_abm" for c in documents[0].chunks)


def test_each_transaction_in_a_multi_transaction_file_gets_its_own_type():
    documents = FunctionalSpecChunker().chunk("bc005.md", _read("clients/bc005.md"))
    by_id = {d.document_id: d for d in documents}

    assert by_id["BC005"].transaction_type == "functional_abm"
    assert by_id["BC005_k"].transaction_type == "key_request"


# --- Group 2: index / chapter documents -------------------------------------


def _kind(text: str) -> str:
    return classify_document_kind(
        text, parse_sections(text), min_links=5, min_density=3.0
    )


def test_ca001a_is_detected_as_an_index_document():
    """31+ links to its children, no Campos/Validaciones of its own."""
    documents = FunctionalSpecChunker().chunk("ca001a.md", _read("policies/ca001a.md"))

    assert all(d.document_kind == "index" for d in documents)
    assert documents[0].child_links, "an index document exposes its children"
    assert "CA047" in documents[0].child_links


def test_a_content_document_is_not_an_index():
    for relative in ["policies/ca014.md", "policies/ca004.md", "clients/bc005.md"]:
        documents = FunctionalSpecChunker().chunk(Path(relative).name, _read(relative))
        assert all(d.document_kind == "content" for d in documents), relative


def test_index_documents_still_produce_chunks():
    """Marking, not dropping: misclassifying content as an index would silently
    remove business rules, so retrieval decides what to do with these."""
    documents = FunctionalSpecChunker().chunk("ca001a.md", _read("policies/ca001a.md"))

    assert any(d.chunks for d in documents)
    assert all(c.metadata.document_kind == "index" for d in documents for c in d.chunks)


def test_a_table_section_rules_out_index_however_many_links():
    """Either signal alone misfires, so both are required. The links sit in
    their own section so the Campos section stays a pure table."""
    links = " ".join(f"[l{i}](ca{i:03d}.html)" for i in range(40))
    text = (
        "# Doc\n\n"
        "## Campos\n| A | B |\n|---|---|\n| x | y |\n\n"
        f"## Páginas asociadas\n\n{links}\n"
    )
    assert _kind(text) == "content"


def test_few_links_rules_out_index_however_dense():
    text = "# Doc\n\n## Función\n\n[a](ca001.html) [b](ca002.html)\n"
    assert _kind(text) == "content"


def test_prose_with_a_handful_of_links_stays_content():
    """A content document citing a few siblings must not become an index."""
    prose = " ".join(["palabra"] * 600)
    text = f"# Doc\n\n## Función\n\n{prose}\n\n[a](ca001.html) [b](ca002.html) [c](ca003.html) [d](ca004.html) [e](ca005.html)\n"
    assert _kind(text) == "content"


def test_extract_child_links_dedupes_and_keeps_order():
    text = "ver [x](ca047.html), [y](ca025.html) y otra vez [x](ca047.html)"
    assert extract_child_links(text) == ["CA047", "CA025"]


# --- Chunks that carry no information ---------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "###  Proceso",  # a leftover section heading
        "#",
        "####  Campo",
        "__",  # an export artifact
        "Información: \nCampo: \nOperador: \nValor: ",  # a table row, all cells empty
        "",
    ],
)
def test_structure_and_emptiness_carry_no_information(body):
    from app.generation.rag.chunking.functional_spec import carries_no_information

    assert carries_no_information(body) is True


@pytest.mark.parametrize(
    "body",
    [
        "No aplica.",
        "A petición del usuario.",
        "Volver a ejecutar.",
        "La tabla es de valores fijos.",
        "Campo: Emisión\nValidación: Debe estar lleno",
        # The export emits '# ' for bullet continuations that DO carry content.
        "# § _Se construye el auxiliar concatenando la información según cada nivel._",
    ],
)
def test_short_but_real_content_is_kept(body):
    """The discriminator is content, not length. Filtering by length would have
    deleted 291 real answers ('No aplica.', 'A petición del usuario.') along
    with the noise."""
    from app.generation.rag.chunking.functional_spec import carries_no_information

    assert carries_no_information(body) is False


def test_no_produced_chunk_is_structure_only():
    from app.generation.rag.chunking.functional_spec import carries_no_information

    for relative in ["policies/ca014.md", "policies/ca001.md", "clients/bc005.md"]:
        for document in FunctionalSpecChunker().chunk(Path(relative).name, _read(relative)):
            for chunk in document.chunks:
                body = chunk.text.split("\n", 2)[2] if chunk.text.count("\n") >= 2 else ""
                assert not carries_no_information(body), f"{chunk.chunk_id}: {body[:40]!r}"

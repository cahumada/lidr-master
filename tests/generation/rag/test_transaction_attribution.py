"""Tests for per-transaction attribution: id patterns, block segmentation, and
the container / key-request rules. Fixtures are real corpus documents."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.generation.rag.chunking.functional_spec import (
    DOCUMENT_ID_PATTERN,
    ID_LINE_PATTERN,
    FunctionalSpecChunker,
    resolve_file_level_code,
    resolve_parent_transaction_code,
    split_transaction_blocks,
)
from app.generation.rag.chunking.normalizer import normalize_line_endings

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


def _read(relative: str) -> str:
    return (DATA_ROOT / relative).read_text(encoding="utf-8")


# --- Group 0: the id patterns must cover the forms that really occur ---------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # The four markup forms observed in the corpus.
        ("`**(CA014)**`", "CA014"),
        ("**`(CPL500)`**", "CPL500"),
        ("`(CA004)`", "CA004"),
        ("\\(`MENU`\\)", "MENU"),
        # Codes the previous pattern could not match.
        ("`**(BC005_k)**`", "BC005_k"),
        ("`**(SG001_K)**`", "SG001_K"),
        ("`**(VI7501_A)**`", "VI7501_A"),
        ("`**(CA13-1)**`", "CA13-1"),
        ("`**(CA001k)**`", "CA001k"),
    ],
)
def test_id_line_matches_every_real_form(line, expected):
    match = ID_LINE_PATTERN.search(line)
    assert match is not None, f"{line!r} should be recognized as an id line"
    assert match.group(1) == expected


@pytest.mark.parametrize(
    "line",
    [
        "Texto normal sin ningún id.",
        "según el capital anterior a la modificación \\(`CAE`\\) y el capital actual",
        "| Campo | Descripción |",
    ],
)
def test_id_line_does_not_match_prose(line):
    assert ID_LINE_PATTERN.search(line) is None


def test_inline_pattern_requires_digits_so_prose_is_not_an_id():
    """A letters-only code is accepted only on a standalone id line: inline,
    `(CAE)` and `(PAE)` are variable names in CA014's prose, not transactions."""
    assert DOCUMENT_ID_PATTERN.search("modificación \\(`CAE`\\) y el capital") is None
    assert DOCUMENT_ID_PATTERN.search("la ventana de (CA003) se activa").group(1) == "CA003"


# --- Group 1: segmentation and attribution ----------------------------------


def test_bc005_splits_into_its_two_transactions():
    """bc005.md carries BC005_k and BC005, each with its own H1 + id block.
    Before this change all 53 chunks were attributed to BC005."""
    documents = FunctionalSpecChunker().chunk("bc005.md", _read("clients/bc005.md"))

    by_id = {d.document_id: d for d in documents}
    assert "BC005_k" in by_id, f"expected BC005_k, got {sorted(by_id)}"
    assert "BC005" in by_id, f"expected BC005, got {sorted(by_id)}"

    # The key-request transaction owns its own Campos/Validaciones chunks.
    key_sections = {c.metadata.section for c in by_id["BC005_k"].chunks}
    assert "Campos" in key_sections
    assert "Validaciones" in key_sections

    # Every chunk is attributed to the transaction whose block it came from.
    for document in documents:
        for chunk in document.chunks:
            assert chunk.metadata.document_id == document.document_id


def test_bc005_links_the_key_request_to_its_main_transaction():
    documents = FunctionalSpecChunker().chunk("bc005.md", _read("clients/bc005.md"))
    by_id = {d.document_id: d for d in documents}

    assert by_id["BC005_k"].parent_transaction_code == "BC005"
    assert by_id["BC005"].parent_transaction_code is None


def test_bc005_preamble_merges_into_the_transaction_it_describes():
    """The preamble resolves to BC005, which the file also declares as a block,
    so it is that transaction's own overview — one document, not two entries
    sharing an id."""
    documents = FunctionalSpecChunker().chunk("bc005.md", _read("clients/bc005.md"))

    assert sorted(d.document_id for d in documents) == ["BC005", "BC005_k"]
    assert [d for d in documents if d.is_container] == []

    main = next(d for d in documents if d.document_id == "BC005")
    sections = {c.metadata.section for c in main.chunks}
    # The preamble's general sections and the block's own sections coexist.
    assert "Función general" in sections
    assert "Función" in sections


def test_a_preamble_matching_no_declared_block_stays_a_container():
    """When the preamble cannot be attributed to any transaction the file
    declares, it is kept as a flagged container rather than discarded or
    copied into the children."""
    text = (
        "# Familia de transacciones\n\n"
        "## Función general\n\nDescribe el conjunto, no una transacción.\n\n"
        "# Primera\n\n`**(ZZ001)**`\n\n## Función\n\nTexto uno.\n\n"
        "# Segunda\n\n`**(ZZ002)**`\n\n## Función\n\nTexto dos.\n"
    )
    documents = FunctionalSpecChunker().chunk("familia_zz.md", text)

    containers = [d for d in documents if d.is_container]
    assert len(containers) == 1
    assert containers[0].document_id == "FAMILIA_ZZ"
    assert containers[0].chunks
    assert sorted(d.document_id for d in documents if not d.is_container) == ["ZZ001", "ZZ002"]


def test_accounting_cpl500_uses_the_code_from_the_content_not_the_filename():
    """The filename carries the module as a prefix; the document says CPL500."""
    documents = FunctionalSpecChunker().chunk(
        "accounting_cpl500.md", _read("accounting/accounting_cpl500.md")
    )

    ids = {d.document_id for d in documents}
    assert ids == {"CPL500"}, f"expected only CPL500, got {sorted(ids)}"
    assert "ACCOUNTING_CPL500" not in ids


def test_single_transaction_documents_still_yield_one_document():
    for filename, expected in [
        ("ca001.md", "CA001k"),
        ("ca004.md", "CA004"),
        ("ca014.md", "CA014"),
    ]:
        documents = FunctionalSpecChunker().chunk(filename, _read(f"policies/{filename}"))
        assert len(documents) == 1, f"{filename} should be one transaction"
        assert documents[0].document_id == expected
        assert documents[0].is_container is False


def test_h1_bullet_continuation_lines_do_not_invent_blocks():
    """The export emits '# ' for bullet continuations ('# § _Se construye..._').
    Segmenting on H1 would split cp002-style documents into bogus blocks;
    segmentation keys on the id line instead."""
    text = normalize_line_endings(
        "# Actualización de cuentas\n\n"
        "## Función general\n\nTexto de la función.\n\n"
        "# · _Adicionalmente, mediante esta transacción..._\n\n"
        "# § _Se construye el auxiliar concatenando..._\n\n"
        "# Clave para actualización de cuentas\n\n"
        "`**(CP002_k)**`\n\n"
        "## Función\n\nSolicita la clave.\n"
    )
    preamble, blocks = split_transaction_blocks(text)

    assert len(blocks) == 1, f"expected 1 transaction block, got {len(blocks)}"
    assert blocks[0][0] == "CP002_k"
    # The block starts at its own title, not at one of the bullet lines.
    assert "Clave para actualización de cuentas" in blocks[0][1]
    assert "Adicionalmente" in preamble


@pytest.mark.parametrize(
    ("relative", "expected_fragment"),
    [
        ("policies/ca014.md", "Coberturas"),
        ("policies/ca001.md", "Solicitud de clave"),
        ("clients/bc005.md", "Cambio"),
    ],
)
def test_the_title_is_never_the_id_block(relative, expected_fragment):
    """Regression: a block starting at its own id line took that line as its
    title, putting `[Documento: OP010 - `**(OP010)**`]` in the contextual header
    of 2968 chunks — saying nothing about what the transaction does. The earlier
    test only asserted the title was non-empty, so it missed this."""
    documents = FunctionalSpecChunker().chunk(Path(relative).name, _read(relative))

    for document in documents:
        assert not ID_LINE_PATTERN.match(document.document_title.strip()), (
            f"{document.document_id} title is its id block: {document.document_title!r}"
        )
    assert any(expected_fragment in d.document_title for d in documents), (
        f"expected a real title containing {expected_fragment!r}, "
        f"got {[d.document_title for d in documents]}"
    )


def test_a_block_with_no_title_of_its_own_falls_back_to_the_document_title():
    text = (
        "Coberturas de la póliza individual o certificado\n\n"
        "`(CA014)`\n\n"
        "## Función\n\nPermite consultar y modificar.\n"
    )
    documents = FunctionalSpecChunker().chunk("ca014.md", text)

    assert documents[0].document_title == "Coberturas de la póliza individual o certificado"


def test_document_with_no_id_line_is_a_single_block():
    preamble, blocks = split_transaction_blocks("# Título\n\n## Función\n\nTexto.\n")
    assert (preamble, blocks) == ("", [])


@pytest.mark.parametrize(
    "relative",
    [
        "clients/bc005.md",
        "accounting/accounting_cpl500.md",
        "policies/ca001.md",
        "policies/ca004.md",
        "policies/ca014.md",
    ],
)
def test_chunk_ids_are_unique_within_a_file(relative):
    """Regression: attributing the preamble and a block to the same transaction
    while numbering each from 1 produced duplicate chunk_ids (952 across 223
    corpus files). Everything under one document_id shares one counter."""
    documents = FunctionalSpecChunker().chunk(Path(relative).name, _read(relative))
    ids = [c.chunk_id for d in documents for c in d.chunks]

    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert duplicates == [], f"duplicate chunk_ids: {duplicates[:5]}"


def test_a_container_merged_into_its_transaction_is_no_longer_flagged_container():
    """accounting_cpl500.md's preamble resolves to CPL500, the same transaction
    its block declares, so they become one document rather than two entries
    sharing an id."""
    documents = FunctionalSpecChunker().chunk(
        "accounting_cpl500.md", _read("accounting/accounting_cpl500.md")
    )

    assert len(documents) == 1
    assert documents[0].document_id == "CPL500"
    assert documents[0].is_container is False
    # The preamble's own sections survive inside the merged document.
    sections = {c.metadata.section for c in documents[0].chunks}
    assert any("Función" in s for s in sections)


# --- The resolution rules, in isolation -------------------------------------


@pytest.mark.parametrize(
    ("filename", "found", "expected"),
    [
        # The stem names a declared code -> use it.
        ("bc005.md", ["BC005_k", "BC005"], "BC005"),
        # Stem is polluted by the module prefix, one code declared -> use it.
        ("accounting_cpl500.md", ["CPL500"], "CPL500"),
        # Stem is not declared and several codes exist -> no basis to pick one.
        ("btc001_1.md", ["BTC001", "BTC001_k"], "BTC001_1"),
        # Nothing declared -> the stem is all there is.
        ("ca014.md", [], "CA014"),
    ],
)
def test_resolve_file_level_code(filename, found, expected):
    assert resolve_file_level_code(filename, found) == expected


@pytest.mark.parametrize(
    ("code", "found", "expected"),
    [
        ("BC005_k", ["BC005", "BC005_k"], "BC005"),
        ("SG001_K", ["SG001", "SG001_K"], "SG001"),
        # No base in the same file -> no evidence, so no parent is invented.
        ("OP999_k", ["OP999_k"], None),
        ("CA014", ["CA014"], None),
    ],
)
def test_resolve_parent_transaction_code(code, found, expected):
    assert resolve_parent_transaction_code(code, found) == expected

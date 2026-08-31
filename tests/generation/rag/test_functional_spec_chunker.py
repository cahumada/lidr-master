"""Tests for app.generation.rag.chunking.functional_spec, run against the 3
real functional-spec documents (ca001.md, ca004.md, ca014.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.generation.rag.chunking.base import count_tokens
from app.generation.rag.chunking.functional_spec import (
    NARRATIVE_TOKEN_CAP,
    FunctionalSpecChunker,
    parse_markdown_table,
    parse_sections,
)
from app.generation.rag.chunking.normalizer import normalize_line_endings, repair_broken_tables

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"
DOCUMENTS = ["ca001.md", "ca004.md", "ca014.md"]


@pytest.fixture(scope="module", params=DOCUMENTS)
def document(request) -> tuple[str, str]:
    filename = request.param
    content = (DATA_DIR / filename).read_text(encoding="utf-8")
    return filename, content


@pytest.fixture(scope="module")
def chunked(document) -> tuple[str, str, str, list]:
    filename, content = document
    documents = FunctionalSpecChunker().chunk(filename, content)
    # These three fixtures are single-transaction documents.
    # || Estos tres fixtures son documentos de una sola transacción.
    assert len(documents) == 1
    only = documents[0]
    return filename, only.document_id, only.document_title, only.chunks


def test_document_id_and_title_are_extracted(chunked):
    filename, document_id, title, _chunks = chunked
    expected_id = {"ca001.md": "CA001k", "ca004.md": "CA004", "ca014.md": "CA014"}[filename]
    assert document_id == expected_id
    assert title  # non-empty


def test_no_narrative_chunk_exceeds_the_token_cap(chunked):
    _filename, _document_id, _title, chunks = chunked
    narrative = [c for c in chunks if c.metadata.chunk_type == "narrative"]
    assert narrative, "expected at least one narrative chunk"
    offenders = [(c.chunk_id, c.token_count) for c in narrative if c.token_count > NARRATIVE_TOKEN_CAP]
    assert offenders == [], f"chunks over the {NARRATIVE_TOKEN_CAP}-token cap: {offenders}"


def test_every_chunk_carries_the_contextual_header(chunked):
    _filename, document_id, _title, chunks = chunked
    for chunk in chunks:
        assert chunk.text.startswith(f"[Documento: {document_id} - ")
        assert "[Sección: " in chunk.text


def test_every_chunk_token_count_matches_its_text(chunked):
    _filename, _document_id, _title, chunks = chunked
    for chunk in chunks:
        assert chunk.token_count == count_tokens(chunk.text)


@pytest.mark.parametrize("filename", DOCUMENTS)
def test_campos_and_validaciones_produce_exactly_one_chunk_per_row(filename):
    content = (DATA_DIR / filename).read_text(encoding="utf-8")
    chunks = [c for d in FunctionalSpecChunker().chunk(filename, content) for c in d.chunks]

    # Recompute the expected row counts independently, straight from the
    # (normalized) source table, rather than trusting the chunker's own count.
    # dict() is safe here only because these 3 fixtures have each heading once.
    text = repair_broken_tables(normalize_line_endings(content))
    sections = dict(parse_sections(text))

    for section in ("Campos", "Validaciones"):
        if section not in sections:
            continue
        _headers, rows = parse_markdown_table(sections[section])
        chunk_count = sum(
            1
            for c in chunks
            if c.metadata.section == section and c.metadata.chunk_type == "table"
        )
        assert chunk_count == len(rows), f"{filename}/{section}: expected {len(rows)} row chunks, got {chunk_count}"


def test_ca001_extracts_the_cac011_inline_reference():
    content = (DATA_DIR / "ca001.md").read_text(encoding="utf-8")
    chunks = [c for d in FunctionalSpecChunker().chunk("ca001.md", content) for c in d.chunks]

    found = [
        ref
        for chunk in chunks
        for ref in chunk.references
        if ref.code == "CAC011"
    ]
    assert found, "expected a chunk referencing `CAC011`"
    assert all(ref.type == "inline_transaction" for ref in found)
    assert all(ref.context for ref in found)


def test_ca014_extracts_the_df009_footnote_tag_reference():
    content = (DATA_DIR / "ca014.md").read_text(encoding="utf-8")
    chunks = [c for d in FunctionalSpecChunker().chunk("ca014.md", content) for c in d.chunks]

    found = [ref for chunk in chunks for ref in chunk.references if ref.code == "DF009"]
    assert found, "expected a chunk referencing <DF009>"
    assert all(ref.type == "footnote_tag" for ref in found)


def test_no_chunk_references_its_own_document_id(chunked):
    _filename, document_id, _title, chunks = chunked
    for chunk in chunks:
        assert all(ref.code != document_id for ref in chunk.references)

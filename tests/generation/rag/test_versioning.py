"""Tests for corpus version identity and content hashing — what makes a
client's updated document ingestable without blindly overwriting the old one."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.generation.rag.chunking.functional_spec import FunctionalSpecChunker, content_hash

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


def _read(relative: str) -> str:
    return (DATA_ROOT / relative).read_text(encoding="utf-8")


@pytest.fixture
def chunker() -> FunctionalSpecChunker:
    return FunctionalSpecChunker(tenant_id="acme_seguros", doc_version="DW Funtionals 2026.1")


# --- Version identity reaches the row the vector store will filter ----------


def test_every_chunk_carries_tenant_and_version(chunker):
    """The manifest declares them once, but a vector store filters PER ROW:
    without these on the chunk there is no way to isolate one client."""
    documents = chunker.chunk("ca014.md", _read("policies/ca014.md"))

    for document in documents:
        for chunk in document.chunks:
            assert chunk.metadata.tenant_id == "acme_seguros"
            assert chunk.metadata.doc_version == "DW Funtionals 2026.1"


def test_no_chunk_keeps_the_placeholder_defaults(chunker):
    """The model defaults exist only so the chunk-building functions need not
    thread tenant/version through five signatures. They must never survive."""
    documents = chunker.chunk("ca001.md", _read("policies/ca001.md"))

    for document in documents:
        for chunk in document.chunks:
            assert chunk.metadata.tenant_id != "default"
            assert chunk.metadata.doc_version != "unversioned"
            assert chunk.metadata.content_hash != ""


def test_a_merged_document_stamps_every_chunk_it_absorbed(chunker):
    """Regression: a document that absorbs a further block (its preamble plus
    its own block) had the second batch stamped with only two fields, leaving
    27813 chunks without tenant/version and without breadcrumb. Both paths must
    stamp identically."""
    documents = chunker.chunk("accounting_cpl500.md", _read("accounting/accounting_cpl500.md"))

    assert len(documents) == 1, "this fixture merges a preamble into its block"
    document = documents[0]
    assert len(document.chunks) > 1

    stamped = {
        (c.metadata.tenant_id, c.metadata.doc_version, c.metadata.transaction_type)
        for c in document.chunks
    }
    assert len(stamped) == 1, f"chunks of one document disagree on their stamp: {stamped}"
    assert stamped == {("acme_seguros", "DW Funtionals 2026.1", "process_report")}


def test_two_tenants_produce_distinguishable_chunks():
    """Same document, two clients: the chunk_id repeats — it is a locator, not
    an identity — so the tenant is what keeps the rows apart."""
    content = _read("policies/ca004.md")
    a = FunctionalSpecChunker(tenant_id="client_a", doc_version="v1").chunk("ca004.md", content)
    b = FunctionalSpecChunker(tenant_id="client_b", doc_version="v1").chunk("ca004.md", content)

    assert a[0].chunks[0].chunk_id == b[0].chunks[0].chunk_id
    assert a[0].chunks[0].metadata.tenant_id != b[0].chunks[0].metadata.tenant_id


# --- Content hashing: the point is not paying twice for what did not change --


def test_content_hash_is_stable_across_runs(chunker):
    """Same input, same hash — otherwise incremental re-ingest is impossible."""
    content = _read("policies/ca004.md")
    first = chunker.chunk("ca004.md", content)
    second = chunker.chunk("ca004.md", content)

    assert first[0].content_hash == second[0].content_hash
    assert [c.metadata.content_hash for c in first[0].chunks] == [
        c.metadata.content_hash for c in second[0].chunks
    ]


def test_the_document_hash_ignores_changes_that_normalize_away(chunker):
    """Windows line endings normalize to \\n before hashing, so a re-export that
    only changed line endings must not look like a content change."""
    content = _read("policies/ca004.md")
    as_windows = content.replace("\n", "\r\n")

    assert chunker.chunk("ca004.md", content)[0].content_hash == (
        chunker.chunk("ca004.md", as_windows)[0].content_hash
    )


def test_the_document_hash_changes_when_the_content_changes(chunker):
    original = _read("policies/ca004.md")
    edited = original.replace("Debe estar lleno.", "Debe estar lleno y ser posterior a hoy.", 1)
    assert edited != original

    assert chunker.chunk("ca004.md", original)[0].content_hash != (
        chunker.chunk("ca004.md", edited)[0].content_hash
    )


def test_the_chunk_hash_covers_exactly_what_gets_embedded(chunker):
    """It hashes `text`, header included — the bytes the embeddings API sees."""
    document = chunker.chunk("ca014.md", _read("policies/ca014.md"))[0]

    for chunk in document.chunks:
        assert chunk.metadata.content_hash == content_hash(chunk.text)


def test_an_updated_document_reuses_the_hashes_of_its_unchanged_chunks(chunker):
    """This is the payoff: editing one validation rule must leave the other
    chunks' hashes untouched, so a re-ingest re-embeds only what changed."""
    original = _read("policies/ca004.md")
    edited = original.replace("Debe ser igual a la fecha del computador.", "Debe ser la fecha de alta.", 1)
    assert edited != original

    before = {c.metadata.content_hash for c in chunker.chunk("ca004.md", original)[0].chunks}
    after = {c.metadata.content_hash for c in chunker.chunk("ca004.md", edited)[0].chunks}

    unchanged = before & after
    assert unchanged, "an edit to one rule must not invalidate every chunk"
    # Only a small part of the document moved.
    assert len(unchanged) > 0.8 * len(before), (
        f"only {len(unchanged)}/{len(before)} chunk hashes survived a one-line edit"
    )


# --- Per-document version fields --------------------------------------------


def test_version_fields_default_to_unset_rather_than_invented(chunker):
    """`source_revision` and `valid_from` come from the client's own revision
    control, which the markdown does not carry. Absent, not fabricated."""
    document = chunker.chunk("ca014.md", _read("policies/ca014.md"))[0]

    assert document.source_revision is None
    assert document.valid_from is None
    assert document.content_hash, "the hash, unlike the revision, is always computable"

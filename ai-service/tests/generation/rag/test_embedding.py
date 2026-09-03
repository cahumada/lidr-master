"""Tests for the embedding layer.

Every test here runs without the network and without ``OPENAI_API_KEY``: the
machinery around the model — batching, resumption, index mapping, verification
— is where the real bugs are, and it must be verified on every run.

|| Todos los tests corren sin red y sin ``OPENAI_API_KEY``: la maquinaria
alrededor del modelo —batching, reanudación, mapeo de índices, verificación— es
donde están los bugs reales, y hay que verificarla en cada corrida.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from app.generation.rag.embedding.embedder import (
    DimensionMismatchError,
    Embedder,
    EmbeddingError,
    HashEmbedder,
    OpenAIEmbedder,
    is_retryable,
)
from app.generation.rag.embedding.runner import (
    CorpusValidationError,
    EmbeddableChunk,
    SidecarVerificationError,
    embed_module,
    estimated_cost_usd,
    load_module_chunks,
    plan_module,
    unique_rows,
    verify_before_embedding,
    verify_written_sidecar,
)
from app.generation.rag.embedding.sidecar import (
    SidecarError,
    empty_index,
    load_sidecar,
    rows_by_hash,
    sidecar_paths,
    write_sidecar,
)
from app.generation.rag.schemas import EmbeddingIndexEntry

DIMS = 16


# --- Helpers -----------------------------------------------------------------


def make_chunk(text: str, *, chunk_id: str | None = None, document_id: str = "CA001", tokens: int = 10):
    return EmbeddableChunk(
        chunk_id=chunk_id or f"{document_id}::seccion::{text[:8]}",
        document_id=document_id,
        tenant_id="acme_seguros",
        doc_version="v1",
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        token_count=tokens,
        text=text,
    )


class CountingEmbedder:
    """A ``HashEmbedder`` that records what it was asked for.

    || Un ``HashEmbedder`` que registra qué se le pidió.
    """

    def __init__(self, dimensions: int = DIMS):
        self._inner = HashEmbedder(dimensions)
        self.model = "counting-hash-embedder"
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return self._inner.embed(texts)


class NullVectorEmbedder:
    """Returns all-zero vectors — the silent failure worth catching.

    || Devuelve vectores en cero — el fallo silencioso que hay que atrapar.
    """

    model = "null-embedder"
    dimensions = DIMS

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimensions for _ in texts]


def run(tmp_path, chunks, embedder, *, batch_size=2, checkpoint_every=0, module="policies"):
    vectors, index = load_sidecar(tmp_path, module)
    plan = plan_module(module, chunks, index)
    return plan, embed_module(
        plan,
        embedder=embedder,
        root=tmp_path,
        existing_vectors=vectors,
        existing_index=index,
        batch_size=batch_size,
        checkpoint_every=checkpoint_every,
    )


# --- The deterministic embedder ----------------------------------------------


def test_the_hash_embedder_is_deterministic_and_needs_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    embedder = HashEmbedder(DIMS)

    first, second = embedder.embed(["mismo texto", "mismo texto"])
    assert first == second
    assert len(first) == DIMS
    assert embedder.embed(["otro"])[0] != first


def test_the_hash_embedder_returns_normalized_vectors():
    """Real embeddings are unit vectors; the fake ones behave the same under
    cosine similarity, so a downstream bug shows up here too."""
    vector = HashEmbedder(DIMS).embed(["texto"])[0]
    assert sum(value * value for value in vector) == pytest.approx(1.0)


def test_the_hash_embedder_satisfies_the_protocol():
    assert isinstance(HashEmbedder(DIMS), Embedder)


# --- The text that gets embedded ---------------------------------------------


def test_the_embedded_text_is_exactly_the_chunk_text(tmp_path):
    """The content_hash covers `text` verbatim. If the embedder saw anything
    else, the hash would stop being evidence that the vector is still valid."""
    chunk = make_chunk("[Documento: CA001]\n[Sección: Función]\nAlta de póliza.")
    embedder = CountingEmbedder()

    run(tmp_path, [chunk], embedder)

    assert embedder.calls == [[chunk.text]]


# --- Deduplication -----------------------------------------------------------


def test_a_repeated_hash_becomes_one_row(tmp_path):
    """8.8% of the real corpus is repeated text ('De lo contrario,' 72 times).
    Same hash is the same text: embedding it twice pays twice for one vector."""
    chunks = [make_chunk("De lo contrario,", chunk_id=f"CA001::x::{i}") for i in range(5)]
    chunks.append(make_chunk("Alta de póliza."))
    embedder = CountingEmbedder()

    plan, result = run(tmp_path, chunks, embedder)

    assert len(plan.rows) == 2
    assert plan.duplicates_saved == 4
    assert result.rows_written == 2
    assert sum(len(call) for call in embedder.calls) == 2


def test_unique_rows_keeps_corpus_order():
    chunks = [make_chunk("b"), make_chunk("a"), make_chunk("b"), make_chunk("c")]
    assert [c.text for c in unique_rows(chunks)] == ["b", "a", "c"]


# --- Sidecar round trip ------------------------------------------------------


def test_the_sidecar_round_trips(tmp_path):
    chunks = [make_chunk(f"regla {i}") for i in range(5)]
    run(tmp_path, chunks, HashEmbedder(DIMS))

    vectors, index = load_sidecar(tmp_path, "policies")
    assert vectors.shape == (5, DIMS)
    assert vectors.dtype == np.float32
    assert len(index.entries) == 5


def test_row_n_of_the_binary_is_entry_n_of_the_index(tmp_path):
    chunks = [make_chunk(f"regla {i}") for i in range(5)]
    run(tmp_path, chunks, HashEmbedder(DIMS))
    vectors, index = load_sidecar(tmp_path, "policies")

    reference = HashEmbedder(DIMS)
    by_hash = {c.content_hash: c.text for c in chunks}
    for row, entry in enumerate(index.entries):
        expected = reference.embed([by_hash[entry.content_hash]])[0]
        assert vectors[row] == pytest.approx(np.array(expected, dtype=np.float32), abs=1e-6)


def test_a_vector_is_found_by_its_content_hash(tmp_path):
    chunks = [make_chunk(f"regla {i}") for i in range(4)]
    run(tmp_path, chunks, HashEmbedder(DIMS))
    vectors, index = load_sidecar(tmp_path, "policies")

    row = rows_by_hash(index)[chunks[2].content_hash]
    expected = HashEmbedder(DIMS).embed([chunks[2].text])[0]
    assert vectors[row] == pytest.approx(np.array(expected, dtype=np.float32), abs=1e-6)


def test_an_incomplete_sidecar_is_reported_not_silently_ignored(tmp_path):
    """Treating a half-written pair as empty would re-bill every vector in it."""
    run(tmp_path, [make_chunk("regla")], HashEmbedder(DIMS))
    vectors_path, _ = sidecar_paths(tmp_path, "policies")
    vectors_path.unlink()

    with pytest.raises(SidecarError, match="incomplete sidecar"):
        load_sidecar(tmp_path, "policies")


def test_writing_mismatched_rows_and_entries_is_refused(tmp_path):
    index = empty_index("policies", "hash-embedder", DIMS)
    index.entries = [
        EmbeddingIndexEntry(
            chunk_id="a", document_id="CA001", tenant_id="t", doc_version="v",
            content_hash="h", token_count=1,
        )
    ]
    with pytest.raises(SidecarError, match="refusing to write"):
        write_sidecar(tmp_path, "policies", np.zeros((3, DIMS), dtype=np.float32), index)


# --- Incremental re-runs -----------------------------------------------------


def test_an_unchanged_corpus_makes_no_calls_at_all(tmp_path):
    """The payoff of content_hash: re-running costs nothing."""
    chunks = [make_chunk(f"regla {i}") for i in range(6)]
    run(tmp_path, chunks, HashEmbedder(DIMS))

    embedder = CountingEmbedder()
    plan, result = run(tmp_path, chunks, embedder)

    assert embedder.calls == []
    assert plan.to_embed == []
    assert result.embedded == 0
    assert result.reused == 6
    assert result.tokens_billed == 0


def test_reordering_chunks_makes_no_calls(tmp_path):
    """Row identity is the hash, not the position."""
    chunks = [make_chunk(f"regla {i}") for i in range(6)]
    run(tmp_path, chunks, HashEmbedder(DIMS))

    embedder = CountingEmbedder()
    run(tmp_path, list(reversed(chunks)), embedder)

    assert embedder.calls == []


def test_only_the_new_chunks_are_embedded(tmp_path):
    original = [make_chunk(f"regla {i}") for i in range(4)]
    run(tmp_path, original, HashEmbedder(DIMS))

    updated = original[:3] + [make_chunk("regla nueva")]
    embedder = CountingEmbedder()
    _, result = run(tmp_path, updated, embedder)

    assert [text for call in embedder.calls for text in call] == ["regla nueva"]
    assert result.embedded == 1
    assert result.reused == 3


def test_a_chunk_that_disappeared_is_dropped_from_the_sidecar(tmp_path):
    original = [make_chunk(f"regla {i}") for i in range(4)]
    run(tmp_path, original, HashEmbedder(DIMS))

    _, result = run(tmp_path, original[:2], HashEmbedder(DIMS))

    assert result.dropped == 2
    vectors, index = load_sidecar(tmp_path, "policies")
    assert vectors.shape[0] == 2
    assert {e.content_hash for e in index.entries} == {c.content_hash for c in original[:2]}


def test_a_reused_vector_is_the_same_vector(tmp_path):
    """Reuse must copy the stored vector, not silently recompute or blank it."""
    chunks = [make_chunk(f"regla {i}") for i in range(3)]
    run(tmp_path, chunks, HashEmbedder(DIMS))
    before, _ = load_sidecar(tmp_path, "policies")

    run(tmp_path, chunks + [make_chunk("nueva")], CountingEmbedder())
    after, index = load_sidecar(tmp_path, "policies")

    by_hash = rows_by_hash(index)
    for row, chunk in enumerate(chunks):
        assert after[by_hash[chunk.content_hash]] == pytest.approx(before[row])


# --- Resumption --------------------------------------------------------------


class FailAfterEmbedder:
    """Succeeds for ``limit`` batches, then fails as a transient error would.

    || Tiene éxito por ``limit`` lotes y después falla como lo haría un error
    transitorio agotado.
    """

    def __init__(self, limit: int, dimensions: int = DIMS):
        self._inner = HashEmbedder(dimensions)
        self.model = "fail-after"
        self.dimensions = dimensions
        self._limit = limit
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls > self._limit:
            raise EmbeddingError("simulated outage")
        return self._inner.embed(texts)


def test_an_interrupted_run_resumes_where_it_stopped(tmp_path):
    chunks = [make_chunk(f"regla {i}") for i in range(8)]

    run(tmp_path, chunks, FailAfterEmbedder(2), batch_size=2, checkpoint_every=1)
    vectors, _ = load_sidecar(tmp_path, "policies")
    assert vectors.shape[0] == 4, "only the batches that succeeded were persisted"

    embedder = CountingEmbedder()
    _, result = run(tmp_path, chunks, embedder, batch_size=2)

    assert result.reused == 4
    assert result.embedded == 4
    assert sum(len(call) for call in embedder.calls) == 4, "the persisted half is not re-embedded"
    assert load_sidecar(tmp_path, "policies")[0].shape[0] == 8


def test_a_failed_batch_does_not_abort_the_run(tmp_path):
    """A 99.8%-embedded corpus plus a report of what is missing beats an
    aborted run."""
    chunks = [make_chunk(f"regla {i}") for i in range(6)]

    _, result = run(tmp_path, chunks, FailAfterEmbedder(1), batch_size=2)

    assert result.embedded == 2
    assert len(result.failed) == 2, "the remaining batches were attempted, not skipped"
    assert result.failed[0].module == "policies"
    assert result.failed[0].chunk_ids
    assert load_sidecar(tmp_path, "policies")[0].shape[0] == 2


def test_a_persisted_sidecar_never_holds_a_row_we_did_not_compute(tmp_path):
    """A failed row is ABSENT, not zero — that is what makes resumption work
    without a separate progress file."""
    chunks = [make_chunk(f"regla {i}") for i in range(6)]
    run(tmp_path, chunks, FailAfterEmbedder(1), batch_size=2)

    vectors, _ = load_sidecar(tmp_path, "policies")
    assert vectors.shape[0] == 2
    assert vectors.any(axis=1).all(), "no all-zero row was persisted"


# --- Verification before spending --------------------------------------------


def test_a_chunk_over_the_model_limit_stops_the_run_before_any_call():
    chunks = [make_chunk("corto", tokens=10), make_chunk("largo", tokens=9000)]

    with pytest.raises(CorpusValidationError, match="8191-token"):
        verify_before_embedding(chunks, max_input_tokens=8191)


def test_an_empty_chunk_stops_the_run():
    with pytest.raises(CorpusValidationError, match="empty text"):
        verify_before_embedding([make_chunk("   ")], max_input_tokens=8191)


def test_a_chunk_without_a_hash_stops_the_run():
    chunk = make_chunk("texto")
    naked = EmbeddableChunk(**{**chunk.__dict__, "content_hash": ""})

    with pytest.raises(CorpusValidationError, match="no content_hash"):
        verify_before_embedding([naked], max_input_tokens=8191)


def test_a_valid_corpus_passes_verification():
    verify_before_embedding([make_chunk(f"regla {i}") for i in range(3)], max_input_tokens=8191)


# --- Verification after writing ----------------------------------------------


def test_a_null_vector_is_caught(tmp_path):
    """A null vector raises nothing on its own: the chunk gets indexed and
    never appears in any result."""
    chunks = [make_chunk("regla")]
    run(tmp_path, chunks, NullVectorEmbedder())
    vectors, index = load_sidecar(tmp_path, "policies")

    with pytest.raises(SidecarVerificationError, match="all-zero"):
        verify_written_sidecar(
            "policies", vectors, index,
            dimensions=DIMS, corpus_hashes={c.content_hash for c in chunks},
        )


def test_a_wrong_dimension_is_caught(tmp_path):
    chunks = [make_chunk("regla")]
    run(tmp_path, chunks, HashEmbedder(DIMS))
    vectors, index = load_sidecar(tmp_path, "policies")

    with pytest.raises(SidecarVerificationError, match="dimension"):
        verify_written_sidecar(
            "policies", vectors, index,
            dimensions=DIMS + 1, corpus_hashes={c.content_hash for c in chunks},
        )


def test_an_index_hash_absent_from_the_corpus_is_caught(tmp_path):
    chunks = [make_chunk("regla")]
    run(tmp_path, chunks, HashEmbedder(DIMS))
    vectors, index = load_sidecar(tmp_path, "policies")

    with pytest.raises(SidecarVerificationError, match="absent from the corpus"):
        verify_written_sidecar(
            "policies", vectors, index, dimensions=DIMS, corpus_hashes={"otro"}
        )


def test_a_duplicate_hash_in_the_index_is_caught(tmp_path):
    chunks = [make_chunk("regla")]
    run(tmp_path, chunks, HashEmbedder(DIMS))
    vectors, index = load_sidecar(tmp_path, "policies")
    index.entries.append(index.entries[0])
    vectors = np.vstack([vectors, vectors[0]])

    with pytest.raises(SidecarVerificationError, match="duplicate hash"):
        verify_written_sidecar(
            "policies", vectors, index,
            dimensions=DIMS, corpus_hashes={c.content_hash for c in chunks},
        )


def test_a_healthy_sidecar_verifies(tmp_path):
    chunks = [make_chunk(f"regla {i}") for i in range(4)]
    run(tmp_path, chunks, HashEmbedder(DIMS))
    vectors, index = load_sidecar(tmp_path, "policies")

    verify_written_sidecar(
        "policies", vectors, index,
        dimensions=DIMS, corpus_hashes={c.content_hash for c in chunks},
    )


# --- OpenAIEmbedder, against a double ----------------------------------------


class FakeResponse:
    def __init__(self, vectors):
        self.data = [
            type("Item", (), {"index": i, "embedding": v})() for i, v in enumerate(vectors)
        ]


class FakeEmbeddings:
    def __init__(self, script):
        self._script = list(script)
        self.inputs: list[list[str]] = []

    # `input` shadows the builtin because that is the OpenAI SDK's own parameter name.
    # || `input` tapa al builtin porque ese es el nombre del parámetro en el SDK de OpenAI.
    def create(self, *, model, input):
        self.inputs.append(list(input))
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return FakeResponse(step)


class FakeClient:
    def __init__(self, script):
        self.embeddings = FakeEmbeddings(script)


class Transient(Exception):
    status_code = 429


class BadRequest(Exception):
    status_code = 400


def openai_embedder(client, **kwargs):
    slept: list[float] = []
    embedder = OpenAIEmbedder(
        client, dimensions=DIMS, retry_base_delay=0.01, sleep=slept.append, **kwargs
    )
    return embedder, slept


def test_a_transient_error_is_retried_with_growing_delays():
    client = FakeClient([Transient(), Transient(), [[0.1] * DIMS]])
    embedder, slept = openai_embedder(client, max_retries=5)

    assert len(embedder.embed(["texto"])) == 1
    assert slept == [0.01, 0.02], "the delay doubles on each attempt"


def test_a_bad_request_is_not_retried():
    """Retrying a 400 or a 401 only delays the diagnosis."""
    client = FakeClient([BadRequest()])
    embedder, slept = openai_embedder(client, max_retries=5)

    with pytest.raises(EmbeddingError):
        embedder.embed(["texto"])
    assert client.embeddings.inputs == [["texto"]], "exactly one attempt"
    assert slept == []


def test_retries_are_bounded():
    client = FakeClient([Transient()] * 10)
    embedder, _ = openai_embedder(client, max_retries=2)

    with pytest.raises(EmbeddingError):
        embedder.embed(["texto"])
    assert len(client.embeddings.inputs) == 3, "the first attempt plus 2 retries"


def test_a_wrong_dimension_from_the_api_fails_immediately():
    """Writing a sidecar with mixed dimensions would corrupt every consumer."""
    client = FakeClient([[[0.1] * (DIMS + 4)]])
    embedder, _ = openai_embedder(client, max_retries=3)

    with pytest.raises(DimensionMismatchError):
        embedder.embed(["texto"])
    assert len(client.embeddings.inputs) == 1, "not retried"


def test_vectors_come_back_in_input_order_even_if_the_api_reorders():
    client = FakeClient([None])
    client.embeddings._script = [None]
    response = FakeResponse([[0.1] * DIMS, [0.2] * DIMS])
    response.data.reverse()
    client.embeddings.create = lambda *, model, input: response

    embedder, _ = openai_embedder(client)
    vectors = embedder.embed(["a", "b"])

    assert vectors[0][0] == pytest.approx(0.1)
    assert vectors[1][0] == pytest.approx(0.2)


def test_a_short_response_is_an_error():
    client = FakeClient([[[0.1] * DIMS]])
    embedder, _ = openai_embedder(client, max_retries=0)

    with pytest.raises(EmbeddingError, match="asked for 2"):
        embedder.embed(["a", "b"])


def test_an_empty_batch_costs_nothing():
    client = FakeClient([])
    embedder, _ = openai_embedder(client)

    assert embedder.embed([]) == []
    assert client.embeddings.inputs == []


def test_which_errors_are_retryable():
    assert is_retryable(Transient())
    assert is_retryable(ConnectionError())
    assert is_retryable(TimeoutError())
    assert not is_retryable(BadRequest())
    assert not is_retryable(ValueError("nada que ver"))


# --- Batching and estimates --------------------------------------------------


def test_chunks_are_sent_in_batches_of_the_configured_size(tmp_path):
    chunks = [make_chunk(f"regla {i}") for i in range(7)]
    embedder = CountingEmbedder()

    run(tmp_path, chunks, embedder, batch_size=3)

    assert [len(call) for call in embedder.calls] == [3, 3, 1]


def test_the_plan_counts_batches_and_tokens_without_calling_anything():
    chunks = [make_chunk(f"regla {i}", tokens=100) for i in range(7)]
    plan = plan_module("policies", chunks, None)

    assert plan.batches(3) == 3
    assert plan.tokens_to_bill == 700
    assert estimated_cost_usd(plan.tokens_to_bill) == pytest.approx(700 / 1_000_000 * 0.02)


def test_the_cost_estimate_matches_the_proposal():
    """5118072 tokens at $0.02/1M is the ~$0.10 the proposal committed to."""
    assert estimated_cost_usd(5_118_072) == pytest.approx(0.10, abs=0.005)


# --- Reading the corpus format -----------------------------------------------


def test_load_module_chunks_reads_the_corpus_shape(tmp_path):
    payload = {
        "module": "policies",
        "documents": [
            {
                "document_id": "CA014",
                "chunks": [
                    {
                        "chunk_id": "CA014::campos::1",
                        "text": "texto",
                        "token_count": 42,
                        "metadata": {
                            "tenant_id": "acme_seguros",
                            "doc_version": "v1",
                            "content_hash": "abc",
                        },
                    }
                ],
            }
        ],
    }
    path = tmp_path / "policies.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    module, chunks = load_module_chunks(path)

    assert module == "policies"
    assert len(chunks) == 1
    assert chunks[0].document_id == "CA014"
    assert chunks[0].content_hash == "abc"
    assert chunks[0].token_count == 42

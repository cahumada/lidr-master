"""End-to-end tests for ``scripts/embed_corpus.py``.

The unit tests cover the layers; these cover the wiring — that ``--dry-run``
really calls nothing, that a run writes a manifest and a report, and that the
exit code tells a caller when something is missing. Still no network and no
``OPENAI_API_KEY``.

|| Tests end-to-end de ``scripts/embed_corpus.py``. Los unitarios cubren las
capas; estos cubren el cableado — que ``--dry-run`` realmente no llame a nada,
que una corrida escriba manifiesto y reporte, y que el código de salida le avise
a quien la invoca cuando falta algo. Sigue sin red y sin ``OPENAI_API_KEY``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from app.generation.rag.embedding.embedder import EmbeddingError, HashEmbedder

REPO_ROOT = Path(__file__).resolve().parents[1]
DIMS = 16


def load_script():
    """Import the script by path — it is not an installed module.

    || Importa el script por ruta — no es un módulo instalado.
    """
    spec = importlib.util.spec_from_file_location(
        "embed_corpus", REPO_ROOT / "scripts" / "embed_corpus.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["embed_corpus"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def corpus(tmp_path) -> Path:
    """A two-module corpus in the shape ``chunk_corpus.py`` writes.

    || Un corpus de dos módulos con la forma que escribe ``chunk_corpus.py``.
    """
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()

    def chunk(text: str, index: int) -> dict:
        return {
            "chunk_id": f"CA001::seccion::{index}",
            "text": text,
            "token_count": 10,
            "metadata": {
                "tenant_id": "acme_seguros",
                "doc_version": "v1",
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            },
        }

    for module, texts in {
        "policies": ["alta de póliza", "baja de póliza", "alta de póliza"],
        "claims": ["denuncia de siniestro"],
    }.items():
        payload = {
            "module": module,
            "documents": [
                {
                    "document_id": "CA001",
                    "chunks": [chunk(text, i) for i, text in enumerate(texts)],
                }
            ],
        }
        (chunks_dir / f"{module}.json").write_text(json.dumps(payload), encoding="utf-8")

    (chunks_dir / "manifest.json").write_text(
        json.dumps(
            {"corpus_id": "test-corpus", "tenant_id": "acme_seguros", "doc_version": "v1"}
        ),
        encoding="utf-8",
    )
    return chunks_dir


@pytest.fixture
def script(monkeypatch):
    module = load_script()
    monkeypatch.setattr(
        module.get_settings(), "EMBEDDING_BATCH_SIZE", 2, raising=False
    )
    return module


def invoke(script, monkeypatch, argv: list[str], embedder=None) -> int:
    monkeypatch.setattr(sys, "argv", ["embed_corpus.py", *argv])
    if embedder is not None:
        import app.dependencies

        monkeypatch.setattr(app.dependencies, "get_embedder", lambda: embedder)
    return script.main()


def test_dry_run_calls_nothing_and_writes_nothing(script, corpus, tmp_path, monkeypatch, capsys):
    out = tmp_path / "embeddings"

    code = invoke(script, monkeypatch, ["--chunks", str(corpus), "--out", str(out), "--dry-run"])

    assert code == 0
    assert not out.exists()
    printed = capsys.readouterr().out
    assert "Rows to embed:      3" in printed, "the repeated text is one row, not two"
    assert "Duplicates saved:   1" in printed
    assert "US$" in printed


def test_dry_run_needs_no_api_key(script, corpus, tmp_path, monkeypatch):
    """The composition root raises without a key; --dry-run must never reach it."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import app.dependencies

    def explode():
        raise AssertionError("--dry-run must not build an embedder")

    monkeypatch.setattr(app.dependencies, "get_embedder", explode)

    out = tmp_path / "embeddings"
    assert invoke(script, monkeypatch, ["--chunks", str(corpus), "--out", str(out), "--dry-run"]) == 0


def test_a_full_run_writes_sidecars_a_manifest_and_a_report(
    script, corpus, tmp_path, monkeypatch
):
    out = tmp_path / "embeddings"

    code = invoke(
        script, monkeypatch, ["--chunks", str(corpus), "--out", str(out)], HashEmbedder(DIMS)
    )

    assert code == 0
    assert (out / "policies.npy").exists()
    assert (out / "policies.index.json").exists()
    assert (out / "claims.npy").exists()
    assert (out / "embedding_report.md").exists()

    manifest = json.loads((out / "embeddings_manifest.json").read_text(encoding="utf-8"))
    assert manifest["corpus_id"] == "test-corpus"
    assert manifest["tenant_id"] == "acme_seguros"
    assert manifest["total_rows"] == 3, "2 rows in policies (one deduped) + 1 in claims"
    assert manifest["embedded_now"] == 3
    assert manifest["failed_batches"] == []


def test_a_second_run_over_an_unchanged_corpus_embeds_nothing(
    script, corpus, tmp_path, monkeypatch, capsys
):
    out = tmp_path / "embeddings"
    invoke(script, monkeypatch, ["--chunks", str(corpus), "--out", str(out)], HashEmbedder(DIMS))
    capsys.readouterr()

    class Forbidden:
        model = "forbidden"
        dimensions = DIMS

        def embed(self, texts):
            raise AssertionError("an unchanged corpus must make no calls")

    code = invoke(script, monkeypatch, ["--chunks", str(corpus), "--out", str(out)], Forbidden())

    assert code == 0
    assert "Nothing to embed" in capsys.readouterr().out


def test_failed_batches_make_the_exit_code_non_zero(script, corpus, tmp_path, monkeypatch):
    class AlwaysFails:
        model = "always-fails"
        dimensions = DIMS

        def embed(self, texts):
            raise EmbeddingError("simulated outage")

    out = tmp_path / "embeddings"
    code = invoke(
        script, monkeypatch, ["--chunks", str(corpus), "--out", str(out)], AlwaysFails()
    )

    assert code == 1
    manifest = json.loads((out / "embeddings_manifest.json").read_text(encoding="utf-8"))
    assert manifest["failed_batches"], "the report must name what is missing"
    assert manifest["total_rows"] == 0


def test_a_module_filter_limits_the_run(script, corpus, tmp_path, monkeypatch):
    out = tmp_path / "embeddings"

    invoke(
        script,
        monkeypatch,
        ["--chunks", str(corpus), "--out", str(out), "--module", "claims"],
        HashEmbedder(DIMS),
    )

    assert (out / "claims.npy").exists()
    assert not (out / "policies.npy").exists()


def test_a_missing_corpus_is_an_error_not_an_empty_success(script, tmp_path, monkeypatch):
    empty = tmp_path / "nada"
    empty.mkdir()

    assert invoke(script, monkeypatch, ["--chunks", str(empty), "--dry-run"]) == 1


def test_a_chunk_over_the_model_limit_stops_the_script(script, corpus, tmp_path, monkeypatch):
    """The check runs during planning, so even --dry-run catches it."""
    from app.generation.rag.embedding.runner import CorpusValidationError

    payload = json.loads((corpus / "claims.json").read_text(encoding="utf-8"))
    payload["documents"][0]["chunks"][0]["token_count"] = 99_999
    (corpus / "claims.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CorpusValidationError):
        invoke(script, monkeypatch, ["--chunks", str(corpus), "--dry-run"])


def test_console_output_survives_a_cp1252_terminal(script, corpus, tmp_path, monkeypatch, capsys):
    """Regression: a single non-ASCII arrow in the closing line aborted a run
    that had already written every sidecar, its manifest and its report. The
    Windows console this runs on is cp1252; the report file keeps the accents."""
    out = tmp_path / "embeddings"
    invoke(script, monkeypatch, ["--chunks", str(corpus), "--out", str(out)], HashEmbedder(DIMS))
    printed = capsys.readouterr()

    (printed.out + printed.err).encode("cp1252")


def test_the_report_file_keeps_its_accents(script, corpus, tmp_path, monkeypatch):
    out = tmp_path / "embeddings"
    invoke(script, monkeypatch, ["--chunks", str(corpus), "--out", str(out)], HashEmbedder(DIMS))

    report = (out / "embedding_report.md").read_text(encoding="utf-8")
    assert "Módulo" in report
    assert "Duplicados ahorrados" in report

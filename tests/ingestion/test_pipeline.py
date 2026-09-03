"""El pipeline: los helpers que estaban duplicados y las guardas de cada paso."""

from __future__ import annotations

import json

import pytest

from app.ingestion.pipeline import (
    EMBEDDING_MANIFEST_FILENAME,
    MANIFEST_FILENAME,
    corpus_identity,
    load_corpus,
    module_files,
)


def test_the_manifest_is_not_a_module(tmp_path):
    """`module_files` globea `*.json` y el manifiesto tambien lo es. Tratarlo
    como un modulo lo trocearia como si tuviera documentos."""
    (tmp_path / "policies.json").write_text("{}", encoding="utf-8")
    (tmp_path / MANIFEST_FILENAME).write_text("{}", encoding="utf-8")

    assert [p.name for p in module_files(tmp_path)] == ["policies.json"]


def test_the_modules_come_back_sorted(tmp_path):
    for name in ("theft", "claims", "policies"):
        (tmp_path / f"{name}.json").write_text("{}", encoding="utf-8")

    assert [p.stem for p in module_files(tmp_path)] == ["claims", "policies", "theft"]


def test_the_identity_comes_from_the_manifest(tmp_path):
    """Del manifiesto y nunca de Settings: el corpus en disco lo produjo una
    corrida concreta, y cargarlo con otra identidad lo atribuiria al cliente
    equivocado."""
    (tmp_path / MANIFEST_FILENAME).write_text(
        json.dumps({"corpus_id": "c1", "tenant_id": "acme", "doc_version": "v9"}),
        encoding="utf-8",
    )

    assert corpus_identity(tmp_path) == ("c1", "acme", "v9")


def test_no_manifest_says_so_instead_of_guessing(tmp_path):
    with pytest.raises(FileNotFoundError, match="chunking"):
        corpus_identity(tmp_path)


def test_pruning_a_partial_corpus_is_refused(tmp_path):
    """Medido una vez sobre un solo modulo: habria borrado 27 de los 28. El tope
    esta en el pipeline y no solo en el script, porque el endpoint corre lo
    mismo."""
    (tmp_path / "policies.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="prune"):
        load_corpus(chunks_dir=tmp_path, modules=["policies"], prune=True)


def test_an_empty_corpus_directory_says_so(tmp_path):
    with pytest.raises(FileNotFoundError, match="No module JSON"):
        load_corpus(chunks_dir=tmp_path)


def test_the_two_manifests_have_different_names():
    """El del corpus y el del sidecar viven en directorios distintos, y
    confundirlos pisaria uno con el otro."""
    assert MANIFEST_FILENAME != EMBEDDING_MANIFEST_FILENAME


# --- La guarda de un solo trabajo, garantizada por la base ---------------------


def test_at_most_one_running_job_is_enforced_by_the_database():
    """El chequeo de la aplicacion da un buen mensaje; ESTO es la garantia.

    La regla sostenida solo en codigo de aplicacion se rompio de verdad: dos
    rebuilds pasaron el chequeo y se trabaron entre si, uno borrando 57101 filas
    y el otro copiando sobre ellas.
    """
    from app.ingestion.jobs import RUNNING, IngestionJobRow

    index = next(
        i for i in IngestionJobRow.__table__.indexes if i.name == "uq_ingestion_jobs_one_running"
    )
    assert index.unique is True
    assert RUNNING in str(index.dialect_options["postgresql"]["where"])

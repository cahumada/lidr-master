"""El pipeline: los helpers que estaban duplicados y las guardas de cada paso."""

from __future__ import annotations

import dataclasses
import json
import json as json_module
from pathlib import Path

import pytest

from app.ingestion.pipeline import (
    EMBEDDING_MANIFEST_FILENAME,
    MANIFEST_FILENAME,
    ChunkStepResult,
    EmbedStepResult,
    LoadStepResult,
    chunk_corpus,
    corpus_dir,
    corpus_identity,
    load_corpus,
    module_files,
    version_slug,
)
from app.ingestion.source import LocalCorpusSource


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
    versionado = corpus_dir(tmp_path, "v9")
    versionado.mkdir(parents=True)
    (versionado / MANIFEST_FILENAME).write_text(
        json.dumps({"corpus_id": "c1", "tenant_id": "acme", "doc_version": "v9"}),
        encoding="utf-8",
    )

    assert corpus_identity(versionado) == ("c1", "acme", "v9")


def test_a_manifest_that_disagrees_with_its_directory_is_an_error(tmp_path):
    """El directorio lleva el nombre de su version, asi que el manifiesto de
    adentro TIENE que coincidir. Si no, alguien movio archivos, y cargar un
    corpus atribuyendolo a otra version no se ve despues: las filas quedan con
    la version equivocada y el prune de la version real las borra."""
    equivocado = corpus_dir(tmp_path, "v1")
    equivocado.mkdir(parents=True)
    (equivocado / MANIFEST_FILENAME).write_text(
        json.dumps({"corpus_id": "c1", "tenant_id": "acme", "doc_version": "v9"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="v9"):
        corpus_identity(equivocado)


def test_two_versions_that_slugify_alike_do_not_share_a_directory():
    """Sin el hash del valor original, "2026.1" y "2026 1" y "2026-1" darian el
    mismo directorio y mezclarian corpus EN SILENCIO."""
    slugs = {version_slug(v) for v in ("2026.1", "2026 1", "2026-1")}
    assert len(slugs) == 3


def test_the_slug_is_a_usable_directory_name():
    """Un doc_version real tiene espacios y puntos, y usarlo crudo obliga a
    entrecomillar cada invocacion de la CLI."""
    slug = version_slug("DW Funtionals 2026.1")
    assert " " not in slug
    assert slug.startswith("dw-funtionals-2026-1-")


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



# --- summary(): el resultado de un paso tiene que ser JSON-serializable ---------
#
# ingestion_jobs.result es JSONB. `asdict()` sobre un ChunkStepResult,
# EmbedStepResult o LoadStepResult deja `out_dir`/`chunks_dir` como un `Path` de
# verdad -- json.dumps no sabe serializarlo -- y eso rompio una corrida real: el
# job e26c7cdc fallo con "Object of type WindowsPath is not JSON serializable" al
# escribir el progreso despues del paso de trocear. `summary()` existe
# especificamente para evitarlo, y sin este test nada impide que un campo `Path`
# nuevo se cuele otra vez sin que `summary()` lo convierta.


def _chunk_result(**overrides) -> ChunkStepResult:
    base = {
        "corpus_id": "c1", "out_dir": Path("data/chunks/v1"), "source": "s3://b",
        "tenant_id": "t", "doc_version": "v1", "modules": 1, "files": 1,
        "documents": 1, "chunks": 1, "tokens": 1,
    }
    base.update(overrides)
    return ChunkStepResult(**base)


def _embed_result(**overrides) -> EmbedStepResult:
    base = {
        "out_dir": Path("data/embeddings/v1"), "modules": 1, "to_embed": 0,
        "reused": 1, "duplicates_saved": 0, "tokens_billed": 0, "batches": 0,
        "estimated_cost_usd": 0.0,
    }
    base.update(overrides)
    return EmbedStepResult(**base)


def _load_result(**overrides) -> LoadStepResult:
    base = {
        "corpus_id": "c1", "chunks_dir": Path("data/chunks/v1"), "tenant_id": "t",
        "doc_version": "v1", "modules": 1, "rows_ready": 1, "distinct_texts": 1,
        "chunks_without_vector": 0,
    }
    base.update(overrides)
    return LoadStepResult(**base)


def test_asdict_alone_leaks_a_real_path_on_chunk_result():
    """Documenta el defecto que `summary()` existe para evitar: `asdict()` a
    secas NO convierte un campo `Path` a texto."""
    leaked = dataclasses.asdict(_chunk_result())["out_dir"]
    assert isinstance(leaked, Path)
    with pytest.raises(TypeError, match="not JSON serializable"):
        json_module.dumps(leaked)


def test_chunk_result_summary_is_json_serializable():
    summary = _chunk_result().summary()
    assert isinstance(summary["out_dir"], str)
    json_module.dumps(summary)  # no debe lanzar


def test_embed_result_summary_is_json_serializable():
    summary = _embed_result().summary()
    assert isinstance(summary["out_dir"], str)
    json_module.dumps(summary)


def test_embed_result_summary_drops_the_non_json_fields():
    """`module_results` son objetos ModuleResult y `manifest` un
    EmbeddingManifest: ninguno de los dos es JSON-serializable, y no hace falta
    que lo sean porque son para el reporte de consola, no para la fila del job."""
    summary = _embed_result().summary()
    assert "module_results" not in summary
    assert "manifest" not in summary


def test_load_result_summary_is_json_serializable():
    summary = _load_result().summary()
    assert isinstance(summary["chunks_dir"], str)
    json_module.dumps(summary)



# --- chunk_corpus: no debe cargar modulos que la fuente ya no tiene ------------
#
# Un rebuild real dejo 24 documentos de 4 modulos que ya no estaban en el bucket
# cargados en Postgres, porque `chunk_corpus` solo ESCRIBE los modulos que
# encuentra y nunca borra el `<modulo>.json` de uno que desaparecio de la
# fuente. `embed_corpus`/`load_corpus` globean *.json sin poder distinguir un
# archivo fresco de uno que sobro.


def test_a_module_removed_from_the_source_is_cleaned_up_on_a_full_run(tmp_path):
    """Corrida completa (sin filtro de modulos): lo que la fuente ya no tiene,
    tampoco debe seguir en el directorio versionado."""
    origen = tmp_path / "fuente"
    (origen / "policies").mkdir(parents=True)
    (origen / "policies" / "ca014.md").write_text("# CA014", encoding="utf-8")

    salida = tmp_path / "chunks"
    chunk_corpus(source=LocalCorpusSource(origen), out_dir=salida, doc_version="v1")
    huerfano_esperado = corpus_dir(salida, "v1") / "civil_liability.json"
    huerfano_esperado.write_text('{"module": "civil_liability", "documents": []}', "utf-8")
    assert huerfano_esperado.exists()

    # Segunda corrida completa: "civil_liability" ya no esta en la fuente.
    chunk_corpus(source=LocalCorpusSource(origen), out_dir=salida, doc_version="v1")

    assert not huerfano_esperado.exists()


def test_a_filtered_run_never_touches_its_siblings(tmp_path):
    """`--module policies` deja a `claims` intacto: un filtro no es evidencia de
    que los demas modulos desaparecieron de la fuente."""
    origen = tmp_path / "fuente"
    for modulo, archivo in (("policies", "ca014.md"), ("claims", "si001.md")):
        d = origen / modulo
        d.mkdir(parents=True)
        (d / archivo).write_text(f"# {archivo}", encoding="utf-8")

    salida = tmp_path / "chunks"
    chunk_corpus(source=LocalCorpusSource(origen), out_dir=salida, doc_version="v1")

    # Corrida FILTRADA a solo "policies": "claims" no se toca aunque no este en
    # el conjunto de modulos de esta corrida.
    chunk_corpus(
        source=LocalCorpusSource(origen), out_dir=salida, doc_version="v1",
        modules=["policies"],
    )

    assert (corpus_dir(salida, "v1") / "claims.json").exists()


def test_removing_orphans_is_reported_not_silent(tmp_path):
    """Borrar un modulo entero de una base de datos, aunque sea de un archivo
    intermedio, no puede pasar sin dejar rastro."""
    import structlog.testing

    origen = tmp_path / "fuente"
    (origen / "policies").mkdir(parents=True)
    (origen / "policies" / "ca014.md").write_text("# CA014", encoding="utf-8")
    salida = tmp_path / "chunks"

    chunk_corpus(source=LocalCorpusSource(origen), out_dir=salida, doc_version="v1")
    (corpus_dir(salida, "v1") / "financing.json").write_text(
        '{"module": "financing", "documents": []}', "utf-8"
    )

    with structlog.testing.capture_logs() as logs:
        chunk_corpus(source=LocalCorpusSource(origen), out_dir=salida, doc_version="v1")

    eventos = [entry for entry in logs if entry.get("event") == "removed_orphaned_module_files"]
    assert len(eventos) == 1
    assert eventos[0]["modules"] == ["financing"]

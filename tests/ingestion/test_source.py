"""Las dos fuentes del corpus, sin red.

El bucket se prueba contra un doble del cliente, no contra S3: un test que
necesita credenciales no se corre, y este modulo no importa boto3 justamente
para que se pueda testear asi.
"""

from __future__ import annotations

import pytest

from app.ingestion.source import (
    CorpusSource,
    LocalCorpusSource,
    S3CorpusSource,
    is_excluded,
    module_of,
)

# --- El criterio compartido ----------------------------------------------------


def test_the_module_is_the_first_segment():
    """Mismo criterio en las dos fuentes. En un bucket es el primer segmento de
    la clave, porque S3 no tiene directorios."""
    assert module_of("policies/ca014.md") == "policies"
    assert module_of("claims/sub/si001.md") == "claims"


def test_the_export_notes_at_the_root_are_excluded():
    assert is_excluded("processing_report.md") is True
    assert is_excluded("prompt_procesamiento_rag.md") is True


def test_the_same_name_inside_a_module_is_not_excluded():
    """Solo en la raiz: adentro de un modulo ya no es la nota del export, y
    excluirlo ahi descartaria un documento real."""
    assert is_excluded("policies/processing_report.md") is False


# --- Un directorio local -------------------------------------------------------


@pytest.fixture
def corpus(tmp_path):
    (tmp_path / "policies").mkdir()
    (tmp_path / "claims").mkdir()
    (tmp_path / "policies" / "ca014.md").write_text("# CA014", encoding="utf-8")
    (tmp_path / "policies" / "ca003.md").write_text("# CA003", encoding="utf-8")
    (tmp_path / "claims" / "si001.md").write_text("# SI001", encoding="utf-8")
    (tmp_path / "processing_report.md").write_text("nota del export", encoding="utf-8")
    (tmp_path / "policies" / "no_es_markdown.txt").write_text("x", encoding="utf-8")
    return tmp_path


def test_the_local_source_groups_by_module(corpus):
    modules = LocalCorpusSource(corpus).modules()

    assert set(modules) == {"policies", "claims"}
    assert len(modules["policies"]) == 2


def test_the_local_source_ignores_what_is_not_markdown(corpus):
    keys = LocalCorpusSource(corpus).modules()["policies"]
    assert all(key.endswith(".md") for key in keys)


def test_the_local_source_reads_a_document(corpus):
    source = LocalCorpusSource(corpus)
    assert source.read("policies/ca014.md") == "# CA014"


def test_the_local_source_labels_itself_by_its_path(corpus):
    assert str(corpus) in LocalCorpusSource(corpus).label()


# --- Un bucket -----------------------------------------------------------------


class FakeS3:
    """Pagina como S3: 1.000 claves por respuesta, con token de continuacion."""

    def __init__(self, keys: list[str], *, page_size: int = 1000) -> None:
        self._keys = keys
        self._page_size = page_size
        self.bodies: dict[str, bytes] = {key: key.encode("utf-8") for key in keys}
        self.pages_served = 0

    def list_objects_v2(self, **request):
        prefix = request.get("Prefix", "")
        matching = [key for key in self._keys if key.startswith(prefix)]
        start = int(request.get("ContinuationToken", 0))
        page = matching[start : start + self._page_size]
        self.pages_served += 1
        nxt = start + self._page_size
        truncated = nxt < len(matching)
        response = {"Contents": [{"Key": key} for key in page], "IsTruncated": truncated}
        if truncated:
            response["NextContinuationToken"] = str(nxt)
        return response

    def get_object(self, **request):
        class Body:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self) -> bytes:
                return self._data

        return {"Body": Body(self.bodies[request["Key"]])}


def test_the_bucket_source_groups_by_the_key_prefix():
    client = FakeS3(["policies/ca014.md", "policies/ca003.md", "claims/si001.md"])

    modules = S3CorpusSource(client, bucket="b").modules()

    assert set(modules) == {"policies", "claims"}
    assert len(modules["policies"]) == 2


def test_the_listing_is_paginated():
    """`list_objects_v2` devuelve 1.000 claves por pagina y el corpus tiene
    2.169 documentos. Sin paginar se perderian mas de la mitad EN SILENCIO."""
    keys = [f"policies/doc{i:05d}.md" for i in range(2169)]
    client = FakeS3(keys)

    modules = S3CorpusSource(client, bucket="b").modules()

    assert len(modules["policies"]) == 2169
    assert client.pages_served == 3


def test_a_truncated_listing_without_a_token_is_an_error():
    """La respuesta se contradice, y devolver lo que hay seria devolver un
    corpus incompleto sin avisar."""

    class Contradictory:
        def list_objects_v2(self, **_request):
            return {"Contents": [{"Key": "policies/a.md"}], "IsTruncated": True}

    with pytest.raises(RuntimeError, match="continuation token"):
        S3CorpusSource(Contradictory(), bucket="b").modules()


def test_the_prefix_is_normalised():
    """S3 no tiene directorios, asi que "policies", "/policies" y "policies/"
    son prefijos DISTINTOS y solo uno matchea las claves reales."""
    keys = ["corpus/policies/ca014.md"]
    for prefix in ("corpus", "/corpus", "corpus/", "/corpus/"):
        modules = S3CorpusSource(FakeS3(keys), bucket="b", prefix=prefix).modules()
        assert set(modules) == {"policies"}, prefix


def test_a_key_with_no_module_is_skipped_not_guessed():
    """Adivinarle un modulo lo atribuiria al equivocado."""
    client = FakeS3(["suelto.md", "policies/ca014.md"])

    modules = S3CorpusSource(client, bucket="b").modules()

    assert set(modules) == {"policies"}


def test_the_bucket_source_reads_a_document():
    client = FakeS3(["policies/ca014.md"])
    assert S3CorpusSource(client, bucket="b").read("policies/ca014.md") == "policies/ca014.md"


def test_a_bad_byte_does_not_abort_the_run():
    """Un byte malo en un documento no puede abortar una corrida de 2.169."""
    client = FakeS3(["policies/ca014.md"])
    client.bodies["policies/ca014.md"] = b"# CA014 \xff invalido"

    assert "CA014" in S3CorpusSource(client, bucket="b").read("policies/ca014.md")


def test_the_bucket_source_labels_itself_by_its_location():
    label = S3CorpusSource(FakeS3([]), bucket="mi-bucket", prefix="corpus").label()
    assert label == "s3://mi-bucket/corpus/"


def test_the_filename_is_what_the_chunker_gets():
    """Es de ahi que sale el id cuando el documento no lo declara, asi que tiene
    que ser el nombre y nunca la clave entera."""
    source = S3CorpusSource(FakeS3([]), bucket="b")
    assert source.name_of("corpus/policies/ca014.md") == "ca014.md"


# --- El contrato ---------------------------------------------------------------


def test_both_sources_satisfy_the_protocol(tmp_path):
    assert isinstance(LocalCorpusSource(tmp_path), CorpusSource)
    assert isinstance(S3CorpusSource(FakeS3([]), bucket="b"), CorpusSource)

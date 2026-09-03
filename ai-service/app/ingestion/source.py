"""De dónde salen los documentos fuente: un directorio o un bucket.

El chunking necesita dos cosas de una fuente, no un sistema de archivos: la
lista de documentos agrupados por módulo, y el texto de uno. Esa es toda la
superficie, y por eso el ``Protocol`` tiene dos métodos.

Esta es la abstracción que `openspec/project.md` dejó anotada como pendiente
—«se agrega cuando entre la segunda estrategia»— y entró la segunda fuente: un
bucket S3-compatible de Railway, con el directorio local que sigue existiendo
para la CLI y los tests.

|| Where the source documents come from: a directory or a bucket.

Chunking needs two things from a source, not a filesystem: the documents grouped
by module, and one document's text. That is the whole surface, which is why the
``Protocol`` has two methods.

This is the abstraction `openspec/project.md` recorded as pending -- "added when
the second strategy arrives" -- and the second source arrived: a Railway
S3-compatible bucket, with the local directory still there for the CLI and the
tests.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)

# Documentación del proyecto que vive en la raíz del corpus y no es una
# especificación funcional: las notas de procesamiento del propio export.
# || Project documentation living at the corpus root and not a functional spec:
# the export's own processing notes.
EXCLUDED_FILENAMES = frozenset({"processing_report.md", "prompt_procesamiento_rag.md"})

SUFFIX = ".md"


@runtime_checkable
class CorpusSource(Protocol):
    """Los documentos fuente, agrupados por módulo.

    || The source documents, grouped by module.
    """

    def modules(self) -> dict[str, list[str]]:
        """``{módulo: [claves]}``, ordenado. || ``{module: [keys]}``, sorted."""
        ...

    def read(self, key: str) -> str:
        """El texto de un documento. || One document's text."""
        ...

    def name_of(self, key: str) -> str:
        """El nombre de archivo de una clave. Es lo que el chunker recibe, porque
        de ahí saca el id cuando el documento no lo declara.

        || A key's filename. It is what the chunker receives, because that is
        where the id comes from when the document does not declare one.
        """
        ...

    def label(self) -> str:
        """De dónde salió este corpus, para el manifiesto.

        || Where this corpus came from, for the manifest.
        """
        ...


def module_of(relative: str) -> str:
    """El primer segmento de la ruta relativa.

    Mismo criterio en las dos fuentes. En un bucket es el primer segmento de la
    clave, porque S3 no tiene directorios: ``policies/ca014.md`` pertenece a
    ``policies`` porque su clave empieza con eso, no porque esté adentro de nada.

    || The first segment of the relative path. Same rule in both sources. In a
    bucket it is the key's first segment, because S3 has no directories.
    """
    return PurePosixPath(relative).parts[0]


def is_excluded(relative: str) -> bool:
    """Un archivo de la raíz que no es una especificación.

    Solo en la raíz: un ``processing_report.md`` adentro de un módulo sí se
    trocea, porque ahí no es la nota del export.

    || A root file that is not a specification. Only at the root: a
    ``processing_report.md`` inside a module IS chunked, because there it is not
    the export's note.
    """
    parts = PurePosixPath(relative).parts
    return len(parts) == 1 and parts[0] in EXCLUDED_FILENAMES


# --- Un directorio local || A local directory ----------------------------------


class LocalCorpusSource:
    """Un directorio en disco. Lo que usan la CLI y los tests.

    Sin red y sin credenciales, que es lo que la mantiene como la fuente de los
    tests: un test que necesita un bucket no se corre.

    || A directory on disk. What the CLI and the tests use. No network and no
    credentials, which is what keeps it as the tests' source: a test that needs a
    bucket does not get run.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def modules(self) -> dict[str, list[str]]:
        """Ordenado por la CLAVE relativa y no por el ``Path``.

        No es un detalle: en Windows ``Path`` compara **sin distinguir
        mayusculas**, asi que ``sorted(rglob(...))`` da
        ``alpha, cag_chunk, README, Zeta``; en Linux da
        ``README, Zeta, alpha, cag_chunk``. El mismo corpus quedaria en otro
        orden segun el sistema operativo, y desplegar en Linux reordenaria en
        silencio lo que en desarrollo se veia de otra forma.

        Ordenar por la clave relativa es platform-independent y es tambien el
        orden que devuelve S3, asi que las dos fuentes producen el corpus
        identico y no solo equivalente.

        || Sorted by the relative KEY and not by the ``Path``. Not a detail: on
        Windows ``Path`` compares case-INSENSITIVELY, so ``sorted(rglob(...))``
        gives one order and Linux gives another. The same corpus would come out
        ordered differently depending on the OS, and deploying to Linux would
        silently reorder what development saw. Sorting by the relative key is
        platform-independent and is also S3's order, so both sources produce an
        identical corpus and not merely an equivalent one.
        """
        grouped: dict[str, list[str]] = {}
        keys = sorted(
            path.relative_to(self._root).as_posix()
            for path in self._root.rglob(f"*{SUFFIX}")
        )
        for relative in keys:
            if is_excluded(relative):
                continue
            grouped.setdefault(module_of(relative), []).append(relative)
        return grouped

    def read(self, key: str) -> str:
        return (self._root / key).read_text(encoding="utf-8")

    def name_of(self, key: str) -> str:
        return PurePosixPath(key).name

    def label(self) -> str:
        return str(self._root)


# --- Un bucket S3-compatible || An S3-compatible bucket ------------------------


class S3CorpusSource:
    """Un bucket S3-compatible: Railway, MinIO o AWS.

    El cliente se inyecta, igual que en ``OpenAIEmbedder`` y ``LLMReranker``:
    este módulo no importa ``boto3``, así que se testea con un doble y sin red.

    || An S3-compatible bucket: Railway, MinIO or AWS. The client is injected,
    the same as in ``OpenAIEmbedder`` and ``LLMReranker``: this module does not
    import ``boto3``, so it is tested with a double and no network.
    """

    def __init__(self, client, *, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def _keys(self) -> list[str]:
        """Todas las claves ``.md`` del bucket, paginadas.

        Paginado a propósito: ``list_objects_v2`` devuelve 1.000 claves por
        página y el corpus tiene 2.169 documentos, así que sin paginar se
        perderían más de la mitad **en silencio**.

        || Every ``.md`` key in the bucket, paginated. Paginated on purpose:
        ``list_objects_v2`` returns 1000 keys per page and the corpus has 2169
        documents, so without paging more than half would go missing SILENTLY.
        """
        keys: list[str] = []
        token: str | None = None
        while True:
            request: dict = {"Bucket": self._bucket}
            if token:
                request["ContinuationToken"] = token
            response = self._client.list_objects_v2(**request)
            for item in response.get("Contents", []):
                if item["Key"].endswith(SUFFIX):
                    keys.append(item["Key"])
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
            if not token:
                # Truncado pero sin token con qué seguir: la respuesta se
                # contradice y devolver lo que hay sería devolver un corpus
                # incompleto sin avisar.
                # || Truncated but with no token to continue: the response
                # contradicts itself, and returning what there is would return
                # an incomplete corpus without saying so.
                raise RuntimeError(
                    f"{self._bucket} said the listing is truncated but gave no "
                    f"continuation token. || {self._bucket} dijo que el listado "
                    f"esta truncado y no dio token para seguir."
                )
        return sorted(keys)

    def modules(self) -> dict[str, list[str]]:
        """El bucket espeja el filesystem: las carpetas de módulo están en la
        raíz, así que la clave ES la ruta relativa.

        || The bucket mirrors the filesystem: the module folders are at the
        root, so the key IS the relative path.
        """
        grouped: dict[str, list[str]] = {}
        for key in self._keys():
            if is_excluded(key):
                continue
            if len(PurePosixPath(key).parts) < 2:
                # Un documento sin módulo. Se reporta y se saltea: adivinarle un
                # módulo lo atribuiria al equivocado.
                # || A document with no module. Reported and skipped: guessing a
                # module for it would attribute it to the wrong one.
                logger.warning("corpus_key_without_module", key=key)
                continue
            grouped.setdefault(module_of(key), []).append(key)
        return grouped

    def read(self, key: str) -> str:
        body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        # `errors="replace"` y no `strict`: un byte malo en un documento no puede
        # abortar una corrida de 2.169. El chunker ya reporta lo que no pudo leer.
        # || `errors="replace"` and not `strict`: one bad byte in one document
        # cannot abort a run of 2169. The chunker already reports what it could
        # not read.
        return body.decode("utf-8", errors="replace")

    def name_of(self, key: str) -> str:
        return PurePosixPath(key).name

    def label(self) -> str:
        return f"s3://{self._bucket}"

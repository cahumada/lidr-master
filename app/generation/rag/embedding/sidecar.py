"""Binary sidecar: where the vectors live, and how a row is identified.

Vectors are NOT inlined in the corpus JSON. 1536 floats serialized as text are
~30 KB per chunk; across 61901 chunks that is ~1.8 GB, and the corpus would
stop being the thing you can open, read and diff -- which is what it is for.

Instead each module gets two files: ``<module>.npy`` (float32, shape
``(n, dims)``) and ``<module>.index.json`` (one entry per row). Row ``n`` of
the binary belongs to entry ``n`` of the index, and the entry identifies its
chunk by ``content_hash``, never by position.

|| Sidecar binario: dónde viven los vectores y cómo se identifica una fila.

Los vectores NO van inline en el corpus JSON. 1536 floats serializados como
texto son ~30 KB por chunk; por 61901 chunks eso es ~1,8 GB, y el corpus
dejaría de ser algo que se puede abrir, leer y diffear — que es para lo que
sirve.

En cambio cada módulo tiene dos archivos: ``<module>.npy`` (float32, forma
``(n, dims)``) y ``<module>.index.json`` (una entrada por fila). La fila ``n``
del binario corresponde a la entrada ``n`` del índice, y la entrada identifica
su chunk por ``content_hash``, nunca por posición.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import structlog

from app.generation.rag.schemas import EmbeddingModuleIndex

logger = structlog.get_logger(__name__)

# float32, not float64: half the bytes and more precision than any embedding
# model actually carries.
# || float32, no float64: la mitad de bytes y más precisión de la que cualquier
# modelo de embeddings realmente lleva.
VECTOR_DTYPE = np.float32


class SidecarError(RuntimeError):
    """The sidecar on disk is not usable as it stands.

    || El sidecar en disco no es usable tal como está.
    """


def sidecar_paths(root: Path, module: str) -> tuple[Path, Path]:
    """``(vectors.npy, index.json)`` for one module.

    || ``(vectors.npy, index.json)`` de un módulo.
    """
    return root / f"{module}.npy", root / f"{module}.index.json"


def load_sidecar(root: Path, module: str) -> tuple[np.ndarray | None, EmbeddingModuleIndex | None]:
    """Read a module's sidecar, or ``(None, None)`` if it does not exist yet.

    Both files must be present and agree on their row count. A half-written
    pair is reported rather than silently treated as empty: silently starting
    over would re-bill every vector in it.

    || Lee el sidecar de un módulo, o ``(None, None)`` si todavía no existe.
    Ambos archivos deben estar y coincidir en la cantidad de filas. Un par
    escrito a medias se reporta en lugar de tratarse como vacío en silencio:
    empezar de cero sin avisar volvería a facturar todos sus vectores.
    """
    vectors_path, index_path = sidecar_paths(root, module)
    if not vectors_path.exists() and not index_path.exists():
        return None, None
    if not vectors_path.exists() or not index_path.exists():
        raise SidecarError(
            f"{module}: incomplete sidecar — "
            f"{vectors_path.name} {'exists' if vectors_path.exists() else 'missing'}, "
            f"{index_path.name} {'exists' if index_path.exists() else 'missing'}"
        )

    vectors = np.load(vectors_path)
    index = EmbeddingModuleIndex.model_validate_json(index_path.read_text(encoding="utf-8"))
    if vectors.shape[0] != len(index.entries):
        raise SidecarError(
            f"{module}: {vectors.shape[0]} vector rows vs {len(index.entries)} index entries"
        )
    return vectors, index


def write_sidecar(
    root: Path, module: str, vectors: np.ndarray, index: EmbeddingModuleIndex
) -> None:
    """Write both files, atomically enough that a crash cannot desync them.

    Each file is written to a temporary name and then replaced, so an
    interrupted write leaves the previous pair intact instead of a truncated
    binary paired with a complete index.

    || Escribe ambos archivos, con la atomicidad suficiente como para que una
    caída no los desincronice. Cada archivo se escribe con un nombre temporal y
    después se reemplaza, así una escritura interrumpida deja el par anterior
    intacto en lugar de un binario truncado apareado con un índice completo.
    """
    if vectors.shape[0] != len(index.entries):
        raise SidecarError(
            f"{module}: refusing to write {vectors.shape[0]} rows against "
            f"{len(index.entries)} index entries"
        )

    root.mkdir(parents=True, exist_ok=True)
    vectors_path, index_path = sidecar_paths(root, module)

    vectors_tmp = vectors_path.with_suffix(".npy.tmp")
    index_tmp = index_path.with_suffix(".json.tmp")
    # Written through an open handle on purpose: given a path, np.save appends
    # its own ".npy" and the temporary file would land somewhere else.
    # || Se escribe por un handle abierto a propósito: si recibe una ruta,
    # np.save le agrega su propio ".npy" y el temporal aterriza en otro lado.
    with vectors_tmp.open("wb") as handle:
        np.save(handle, vectors.astype(VECTOR_DTYPE, copy=False))
    index_tmp.write_text(index.model_dump_json(indent=2), encoding="utf-8")
    vectors_tmp.replace(vectors_path)
    index_tmp.replace(index_path)

    logger.info(
        "sidecar_written", module=module, rows=int(vectors.shape[0]), dimensions=index.dimensions
    )


def rows_by_hash(index: EmbeddingModuleIndex | None) -> dict[str, int]:
    """Map ``content_hash`` to its row number.

    A duplicate hash keeps its FIRST row: the vectors are identical by
    construction, so which one survives does not matter, but picking
    deterministically does.

    || Mapea ``content_hash`` a su número de fila. Un hash duplicado se queda
    con su PRIMERA fila: los vectores son idénticos por construcción, así que
    cuál sobrevive da igual, pero elegir de forma determinística no.
    """
    if index is None:
        return {}
    mapping: dict[str, int] = {}
    for row, entry in enumerate(index.entries):
        mapping.setdefault(entry.content_hash, row)
    return mapping


def empty_index(module: str, model: str, dimensions: int) -> EmbeddingModuleIndex:
    """A fresh index for a module with no sidecar yet.

    || Un índice nuevo para un módulo que todavía no tiene sidecar.
    """
    return EmbeddingModuleIndex(module=module, model=model, dimensions=dimensions, entries=[])

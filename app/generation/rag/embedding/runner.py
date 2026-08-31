"""Planning, verification and the embedding loop itself.

This layer never imports OpenAI: it takes an :class:`Embedder` and drives it.
That is what lets the whole machinery -- batching, resumption, index mapping,
verification -- be tested on every run without the network or an API key.

|| Planificación, verificación y el loop de embeddings en sí.

Esta capa nunca importa OpenAI: recibe un :class:`Embedder` y lo maneja. Eso es
lo que permite testear toda la maquinaria —batching, reanudación, mapeo de
índices, verificación— en cada corrida, sin red y sin clave.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import structlog

from app.generation.rag.embedding.embedder import Embedder, EmbeddingError
from app.generation.rag.embedding.sidecar import (
    VECTOR_DTYPE,
    empty_index,
    load_sidecar,
    rows_by_hash,
    write_sidecar,
)
from app.generation.rag.schemas import (
    EmbeddingIndexEntry,
    EmbeddingModuleIndex,
    FailedBatch,
)

logger = structlog.get_logger(__name__)

# Published price of text-embedding-3-small, used ONLY for the dry-run
# estimate. It is not a contract with the provider and can go stale; nothing
# in the pipeline depends on it being exact.
# || Precio publicado de text-embedding-3-small, usado SOLO para la estimación
# del dry-run. No es un contrato con el proveedor y puede quedar desactualizado;
# nada en el pipeline depende de que sea exacto.
USD_PER_MILLION_TOKENS = 0.02


class CorpusValidationError(RuntimeError):
    """The corpus cannot be embedded as it stands.

    Raised BEFORE the first call: finding out when the API rejects a chunk
    means paying to learn it.

    || El corpus no se puede embeber tal como está. Se levanta ANTES de la
    primera llamada: enterarse cuando la API rechaza un chunk es pagar por
    averiguarlo.
    """


@dataclass(frozen=True)
class EmbeddableChunk:
    """The parts of a chunk this layer needs. || Lo que esta capa necesita de un chunk.

    A flat record rather than the full :class:`~app.generation.rag.schemas.Chunk`
    so the runner does not depend on the shape of the corpus JSON beyond the
    one function that reads it.

    || Un registro plano en vez del :class:`~app.generation.rag.schemas.Chunk`
    completo, para que el runner no dependa de la forma del corpus JSON más allá
    de la única función que lo lee.
    """

    chunk_id: str
    document_id: str
    tenant_id: str
    doc_version: str
    content_hash: str
    token_count: int
    text: str


def load_module_chunks(path: Path) -> tuple[str, list[EmbeddableChunk]]:
    """Read one ``data/chunks/<module>.json`` into flat records.

    || Lee un ``data/chunks/<module>.json`` a registros planos.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks = [
        EmbeddableChunk(
            chunk_id=chunk["chunk_id"],
            document_id=document["document_id"],
            tenant_id=chunk["metadata"]["tenant_id"],
            doc_version=chunk["metadata"]["doc_version"],
            content_hash=chunk["metadata"]["content_hash"],
            token_count=chunk["token_count"],
            text=chunk["text"],
        )
        for document in payload["documents"]
        for chunk in document["chunks"]
    ]
    return payload["module"], chunks


# --- Verification before spending || Verificación antes de gastar ------------


def verify_before_embedding(chunks: list[EmbeddableChunk], *, max_input_tokens: int) -> None:
    """Check every chunk is embeddable, before the first call.

    || Controla que todo chunk sea embebible, antes de la primera llamada.
    """
    too_long = [c for c in chunks if c.token_count > max_input_tokens]
    if too_long:
        offenders = ", ".join(f"{c.chunk_id} ({c.token_count} tokens)" for c in too_long[:5])
        raise CorpusValidationError(
            f"{len(too_long)} chunk(s) exceed the model's {max_input_tokens}-token "
            f"input limit: {offenders}"
        )

    empty = [c for c in chunks if not c.text.strip()]
    if empty:
        offenders = ", ".join(c.chunk_id for c in empty[:5])
        raise CorpusValidationError(f"{len(empty)} chunk(s) have empty text: {offenders}")

    missing_hash = [c for c in chunks if not c.content_hash]
    if missing_hash:
        offenders = ", ".join(c.chunk_id for c in missing_hash[:5])
        raise CorpusValidationError(
            f"{len(missing_hash)} chunk(s) carry no content_hash: {offenders}"
        )


def unique_rows(chunks: list[EmbeddableChunk]) -> list[EmbeddableChunk]:
    """One row per distinct ``content_hash``, in corpus order.

    Same hash means, by construction, the same text: embedding it twice returns
    the same vector and is billed twice. In the real corpus this is 5451 of
    61901 rows (8.8%).

    || Una fila por ``content_hash`` distinto, en orden de corpus. Mismo hash es,
    por construcción, mismo texto: embeberlo dos veces devuelve el mismo vector y
    se paga dos veces. En el corpus real son 5451 de 61901 filas (8,8%).
    """
    seen: set[str] = set()
    rows: list[EmbeddableChunk] = []
    for chunk in chunks:
        if chunk.content_hash not in seen:
            seen.add(chunk.content_hash)
            rows.append(chunk)
    return rows


# --- Planning || Planificación -----------------------------------------------


@dataclass
class ModulePlan:
    """What a module's run would do, computed without calling anything.

    || Lo que haría la corrida de un módulo, calculado sin llamar a nada.
    """

    module: str
    rows: list[EmbeddableChunk]
    to_embed: list[EmbeddableChunk]
    reused: int
    dropped: int
    duplicates_saved: int

    @property
    def tokens_to_bill(self) -> int:
        return sum(chunk.token_count for chunk in self.to_embed)

    def batches(self, batch_size: int) -> int:
        return -(-len(self.to_embed) // batch_size) if batch_size > 0 else 0


def plan_module(
    module: str, chunks: list[EmbeddableChunk], existing: EmbeddingModuleIndex | None
) -> ModulePlan:
    """Set arithmetic over ``content_hash``: reuse, embed, drop.

    Position is deliberately not used. A regenerated corpus can add, move or
    drop chunks; binding a vector to its position would silently repoint it at
    a different text.

    || Aritmética de conjuntos sobre ``content_hash``: reutilizar, embeber,
    descartar. La posición no se usa a propósito. Un corpus regenerado puede
    agregar, mover o eliminar chunks; atar un vector a su posición lo
    reapuntaría a otro texto en silencio.
    """
    rows = unique_rows(chunks)
    known = set(rows_by_hash(existing))
    corpus_hashes = {chunk.content_hash for chunk in rows}

    return ModulePlan(
        module=module,
        rows=rows,
        to_embed=[chunk for chunk in rows if chunk.content_hash not in known],
        reused=len(corpus_hashes & known),
        dropped=len(known - corpus_hashes),
        duplicates_saved=len(chunks) - len(rows),
    )


# --- Running || Corrida ------------------------------------------------------


@dataclass
class ModuleResult:
    """What a module's run actually did. || Lo que la corrida de un módulo hizo."""

    module: str
    rows_written: int
    embedded: int
    reused: int
    dropped: int
    duplicates_saved: int
    tokens_billed: int
    failed: list[FailedBatch] = field(default_factory=list)


def _entry(chunk: EmbeddableChunk) -> EmbeddingIndexEntry:
    return EmbeddingIndexEntry(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        tenant_id=chunk.tenant_id,
        doc_version=chunk.doc_version,
        content_hash=chunk.content_hash,
        token_count=chunk.token_count,
    )


def embed_module(
    plan: ModulePlan,
    *,
    embedder: Embedder,
    root: Path,
    existing_vectors: np.ndarray | None,
    existing_index: EmbeddingModuleIndex | None,
    batch_size: int,
    checkpoint_every: int,
) -> ModuleResult:
    """Embed a module's pending rows, persisting progress as it goes.

    A batch that exhausts its retries is recorded and the run CONTINUES: its
    hashes simply stay out of the sidecar, so the next run picks them up by the
    same incremental mechanism.

    || Embebe las filas pendientes de un módulo, persistiendo el progreso sobre
    la marcha. Un lote que agota sus reintentos se registra y la corrida SIGUE:
    sus hashes simplemente quedan fuera del sidecar, así que la corrida
    siguiente los toma por el mismo mecanismo incremental.
    """
    dimensions = embedder.dimensions
    known_rows = rows_by_hash(existing_index)

    vectors = np.zeros((len(plan.rows), dimensions), dtype=VECTOR_DTYPE)
    filled = np.zeros(len(plan.rows), dtype=bool)

    for position, chunk in enumerate(plan.rows):
        source_row = known_rows.get(chunk.content_hash)
        if source_row is not None and existing_vectors is not None:
            vectors[position] = existing_vectors[source_row]
            filled[position] = True

    pending = [
        (position, chunk) for position, chunk in enumerate(plan.rows) if not filled[position]
    ]

    failed: list[FailedBatch] = []
    embedded = 0
    tokens_billed = 0
    batches_since_checkpoint = 0

    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        try:
            batch_vectors = embedder.embed([chunk.text for _, chunk in batch])
        except EmbeddingError as error:
            failed.append(
                FailedBatch(
                    module=plan.module,
                    size=len(batch),
                    error=str(error),
                    chunk_ids=[chunk.chunk_id for _, chunk in batch],
                )
            )
            logger.error(
                "embedding_batch_failed",
                module=plan.module,
                size=len(batch),
                error=str(error),
            )
            continue

        for (position, chunk), vector in zip(batch, batch_vectors, strict=True):
            vectors[position] = vector
            filled[position] = True
            tokens_billed += chunk.token_count
        embedded += len(batch)

        batches_since_checkpoint += 1
        if checkpoint_every > 0 and batches_since_checkpoint >= checkpoint_every:
            _persist(root, plan, vectors, filled, dimensions, embedder.model)
            batches_since_checkpoint = 0
            logger.info("embedding_checkpoint", module=plan.module, rows=int(filled.sum()))

    rows_written = _persist(root, plan, vectors, filled, dimensions, embedder.model)

    return ModuleResult(
        module=plan.module,
        rows_written=rows_written,
        embedded=embedded,
        reused=plan.reused,
        dropped=plan.dropped,
        duplicates_saved=plan.duplicates_saved,
        tokens_billed=tokens_billed,
        failed=failed,
    )


def _persist(
    root: Path,
    plan: ModulePlan,
    vectors: np.ndarray,
    filled: np.ndarray,
    dimensions: int,
    model: str,
) -> int:
    """Write only the rows that actually have a vector.

    The sidecar on disk therefore never contains a row we did not compute — a
    failed or not-yet-reached row is ABSENT, not zero. That is what makes an
    interrupted run resumable without a separate progress file.

    || Escribe solo las filas que realmente tienen vector. El sidecar en disco
    nunca contiene una fila que no calculamos — una fila fallida o todavía no
    alcanzada está AUSENTE, no en cero. Eso es lo que hace reanudable una
    corrida interrumpida sin un archivo de progreso aparte.
    """
    kept = np.flatnonzero(filled)
    index = empty_index(plan.module, model, dimensions)
    index.entries = [_entry(plan.rows[int(position)]) for position in kept]
    write_sidecar(root, plan.module, vectors[kept], index)
    return int(kept.size)


# --- Verification after writing || Verificación después de escribir ----------


class SidecarVerificationError(RuntimeError):
    """The written sidecar does not hold up. || El sidecar escrito no se sostiene."""


def verify_written_sidecar(
    module: str,
    vectors: np.ndarray,
    index: EmbeddingModuleIndex,
    *,
    dimensions: int,
    corpus_hashes: set[str],
) -> None:
    """Catch the silent failures: a null vector, a wrong dimension, a stale row.

    A null vector does not raise anything: the chunk gets indexed and never
    appears in any result. That failure is caught here, not in production.

    || Atrapa los fallos silenciosos: un vector nulo, una dimensión equivocada,
    una fila vieja. Un vector nulo no levanta nada: el chunk se indexa y nunca
    aparece en ningún resultado. Ese fallo se detecta acá, no en producción.
    """
    problems: list[str] = []

    if vectors.shape[0] != len(index.entries):
        problems.append(f"{vectors.shape[0]} rows vs {len(index.entries)} index entries")
    if vectors.size and vectors.shape[1] != dimensions:
        problems.append(f"dimension {vectors.shape[1]}, expected {dimensions}")

    if vectors.size:
        null_rows = np.flatnonzero(~vectors.any(axis=1))
        if null_rows.size:
            problems.append(
                f"{null_rows.size} all-zero vector(s), first at row {int(null_rows[0])}"
            )

    hashes = [entry.content_hash for entry in index.entries]
    unknown = [h for h in hashes if h not in corpus_hashes]
    if unknown:
        problems.append(f"{len(unknown)} index hash(es) absent from the corpus, e.g. {unknown[0]}")
    if len(set(hashes)) != len(hashes):
        problems.append(f"{len(hashes) - len(set(hashes))} duplicate hash(es) in the index")

    if problems:
        raise SidecarVerificationError(f"{module}: " + "; ".join(problems))


def verify_module_on_disk(
    root: Path, module: str, *, dimensions: int, corpus_hashes: set[str]
) -> int:
    """Re-read a module's sidecar from disk and verify it.

    || Relee el sidecar de un módulo desde disco y lo verifica.
    """
    vectors, index = load_sidecar(root, module)
    if vectors is None or index is None:
        return 0
    verify_written_sidecar(
        module, vectors, index, dimensions=dimensions, corpus_hashes=corpus_hashes
    )
    return int(vectors.shape[0])


def estimated_cost_usd(tokens: int) -> float:
    """Dry-run cost estimate. || Estimación de costo para el dry-run."""
    return tokens / 1_000_000 * USD_PER_MILLION_TOKENS

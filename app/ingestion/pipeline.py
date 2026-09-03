"""The corpus pipeline in one place: chunk, embed, load, map.

This orchestration used to live inside three scripts' ``main()``, mixed with
argument parsing, report building and ``print``. An HTTP endpoint that needs the
same sequence had two options: import it, or reimplement it. Reimplementing it
means two pipelines that drift, and the one that breaks quietly is the one
nobody runs by hand.

So the seam is:

======================  ==================================================
``pipeline.py``         what to do, and return a structured result
the scripts             how to report it to a console
the endpoint            how to report it to a job row
======================  ==================================================

Every step reports through ``progress`` instead of printing, which is what lets
the same code write to a terminal and to Postgres.

|| El pipeline del corpus en un solo lugar: trocear, embeber, cargar, mapear.

Esta orquestación vivía dentro de los ``main()`` de tres scripts, mezclada con
parseo de argumentos, armado de reportes y ``print``. Un endpoint HTTP que
necesita la misma secuencia tenía dos opciones: importarla o reimplementarla.
Reimplementarla son dos pipelines que divergen, y el que se rompa en silencio va
a ser el que nadie corre a mano.

Cada paso reporta por ``progress`` en lugar de imprimir, que es lo que permite
que el mismo código escriba a una terminal y a Postgres.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import structlog

from app.config import get_settings
from app.generation.rag.chunking.functional_spec import FunctionalSpecChunker
from app.generation.rag.schemas import CorpusManifest, EmbeddingManifest
from app.ingestion.source import CorpusSource

logger = structlog.get_logger(__name__)

# A no-op reporter, so a caller that does not care about progress does not have
# to pass one.
# || Un reportero que no hace nada, para que quien no le importe el progreso no
# tenga que pasar uno.
Progress = Callable[..., None]


def _silent(*_args, **_kwargs) -> None:
    return None


# --- Lo compartido || Shared ---------------------------------------------------

# The corpus directory holds one JSON per module plus two files that are not
# modules. Copied in three scripts before this module existed.
# || El directorio del corpus tiene un JSON por módulo más dos archivos que no
# son módulos. Estaba copiado en tres scripts antes de que existiera este módulo.
NON_MODULE_FILES = frozenset({"manifest.json"})

# Un `doc_version` no es un nombre de directorio: "DW Funtionals 2026.1" tiene
# espacios y puntos, y usarlo crudo obliga a entrecomillar cada invocacion de la
# CLI. Se convierte en slug.
#
# Y el slug lleva un hash corto del valor ORIGINAL, que no es adorno: sin el,
# "2026.1" y "2026 1" y "2026-1" producen el mismo slug y dos versiones
# distintas compartirian directorio, mezclando corpus EN SILENCIO. Es la misma
# clase de fallo que este proyecto viene persiguiendo todo el tiempo.
# || A `doc_version` is not a directory name: "DW Funtionals 2026.1" has spaces
# and dots, and using it raw forces quoting on every CLI invocation. It is
# slugified.
#
# And the slug carries a short hash of the ORIGINAL value, which is not
# decoration: without it "2026.1", "2026 1" and "2026-1" produce the same slug
# and two different versions would share a directory, mixing corpora SILENTLY.
_SLUG_SEPARATORS = re.compile(r"[^a-z0-9]+")


def version_slug(doc_version: str) -> str:
    """A filesystem-safe, collision-free directory name for a ``doc_version``.

    || Un nombre de directorio seguro y sin colisiones para un ``doc_version``.
    """
    plain = doc_version.lower().translate(str.maketrans("aeiounc", "aeiounc"))
    slug = _SLUG_SEPARATORS.sub("-", plain).strip("-") or "unversioned"
    fingerprint = hashlib.sha256(doc_version.encode("utf-8")).hexdigest()[:6]
    return f"{slug}-{fingerprint}"


def corpus_dir(base: Path, doc_version: str) -> Path:
    """Where one documentation version's artifacts live.

    Every generated artifact -- the chunked corpus and the vector sidecar -- goes
    under its version. Without this, re-chunking 2026.2 DESTROYS 2026.1's
    artifacts in place, and with them the ability to reload the previous version
    without paying to embed it again. Demonstrated: of 384 chunks of a first
    corpus, 0 survived chunking a second one over it.

    The tenant is NOT in the path on purpose: one process serves exactly one
    tenant (`Settings.TENANT_ID` is a single value read everywhere), so a
    per-tenant segment would be a directory level that never has a sibling.

    || Donde viven los artefactos de una version de la documentacion. Cada
    artefacto generado va bajo su version. Sin esto, re-trocear 2026.2 DESTRUYE
    los artefactos de 2026.1 en el lugar, y con ellos la posibilidad de recargar
    la version anterior sin volver a pagar por embeberla. Demostrado: de 384
    chunks de un primer corpus, sobrevivieron 0 al trocear un segundo encima.

    El tenant NO va en la ruta a proposito: un proceso sirve exactamente un
    tenant (`Settings.TENANT_ID` es un valor unico leido en todos lados), asi
    que un segmento por tenant seria un nivel de directorio que nunca tiene
    hermanos.
    """
    return base / version_slug(doc_version)


MANIFEST_FILENAME = "manifest.json"
# El del sidecar, que NO es el del corpus: viven en directorios distintos y
# confundirlos pisaria uno con el otro.
# || The sidecar's, which is NOT the corpus's: they live in different
# directories and confusing them would overwrite one with the other.
EMBEDDING_MANIFEST_FILENAME = "embeddings_manifest.json"


def module_files(chunks_dir: Path) -> list[Path]:
    """The per-module corpus JSONs, sorted, without the manifest.

    || Los JSON del corpus por módulo, ordenados, sin el manifiesto.
    """
    return sorted(
        path for path in chunks_dir.glob("*.json") if path.name not in NON_MODULE_FILES
    )


def corpus_identity(chunks_dir: Path) -> tuple[str, str, str]:
    """``(corpus_id, tenant_id, doc_version)`` from the manifest.

    Read from the manifest and never from Settings: the corpus on disk was
    produced by one specific run, and loading it under a different identity
    than the one it was chunked with would attribute it to the wrong client.

    || Se lee del manifiesto y nunca de Settings: el corpus en disco lo produjo
    una corrida concreta, y cargarlo con una identidad distinta a la que se
    troceó lo atribuiría al cliente equivocado.
    """
    manifest_path = chunks_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"{manifest_path} not found. Run the chunking step first. "
            f"|| {manifest_path} no existe. Corré primero el paso de chunking."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = manifest["doc_version"]
    # El directorio lleva el nombre de su version, asi que el manifiesto de
    # adentro TIENE que coincidir. Si no, alguien movio archivos, y cargar un
    # corpus atribuyendolo a otra version es la clase de error que despues no se
    # ve: las filas quedan con la version equivocada y el prune de la version
    # real las borra.
    # || The directory is named after its version, so the manifest inside MUST
    # agree. If it does not, someone moved files, and loading a corpus under the
    # wrong version is the kind of error that does not show up later: the rows
    # carry the wrong version and the real version's prune deletes them.
    if chunks_dir.name and chunks_dir.name != version_slug(declared):
        raise ValueError(
            f"{chunks_dir} holds a manifest for {declared!r}, whose directory would be "
            f"{version_slug(declared)!r}. || {chunks_dir} tiene un manifiesto de "
            f"{declared!r}, cuyo directorio seria {version_slug(declared)!r}."
        )
    return manifest["corpus_id"], manifest["tenant_id"], declared

def chunk_module(
    chunker: FunctionalSpecChunker, source: CorpusSource, module: str, keys: list[str]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Chunk every file in one module.

    Returns (documents, zero_chunk_files, failed_files) — the last two are
    flagged separately in the report since they're the failure modes worth a
    human look (a parseable file that yielded nothing, vs. one that raised).

    || Trocea cada archivo de un módulo. Devuelve (documents,
    zero_chunk_files, failed_files) — las dos últimas se marcan aparte en el
    reporte porque son los modos de falla que ameritan una mirada humana
    (un archivo parseable que no produjo nada, vs. uno que lanzó una excepción).
    """
    documents: list[dict] = []
    zero_chunk_files: list[dict] = []
    failed_files: list[dict] = []

    for key in keys:
        try:
            content = source.read(key)
        except Exception as exc:  # noqa: BLE001 — one unreadable document must
            # not abort a run of 2169. A local read fails differently from a
            # bucket read, so both are caught the same way and reported.
            # || un documento ilegible no puede abortar una corrida de 2169. Una
            # lectura local falla distinto que una de un bucket, así que las dos
            # se capturan igual y se reportan.
            failed_files.append({"file": key, "error": f"read error: {type(exc).__name__}: {exc}"})
            continue
        try:
            chunked = chunker.chunk(source.name_of(key), content)
        except Exception as exc:  # noqa: BLE001 — one bad file must not abort the batch.
            failed_files.append({"file": key, "error": f"{type(exc).__name__}: {exc}"})
            continue

        if not any(doc.chunks for doc in chunked):
            ids = ", ".join(doc.document_id for doc in chunked)
            zero_chunk_files.append({"file": key, "document_id": ids})

        # One source file can describe several transactions, so it contributes
        # one entry per transaction rather than one entry per file.
        # || Un archivo fuente puede describir varias transacciones, así que
        # aporta una entrada por transacción en vez de una por archivo.
        for doc in chunked:
            documents.append(
                {
                    "source_file": source.name_of(key),
                    "module": module,
                    "document_id": doc.document_id,
                    "document_title": doc.document_title,
                    "parent_transaction_code": doc.parent_transaction_code,
                    "is_container": doc.is_container,
                    "transaction_type": doc.transaction_type,
                    "transaction_type_reason": doc.transaction_type_reason,
                    "document_kind": doc.document_kind,
                    "child_links": doc.child_links,
                    "navigation_path": doc.navigation_path,
                    "is_menu_node": doc.is_menu_node,
                    "content_hash": doc.content_hash,
                    "source_revision": doc.source_revision,
                    "valid_from": doc.valid_from.isoformat() if doc.valid_from else None,
                    "chunks": [chunk.model_dump() for chunk in doc.chunks],
                }
            )

    return documents, zero_chunk_files, failed_files


# --- Resultados || Results -----------------------------------------------------


@dataclass
class ChunkStepResult:
    corpus_id: str
    # Donde escribio de verdad, resuelto por version. El reporte del script va
    # aca y no en la base: pertenece a la corrida de esta version.
    # || Where it actually wrote, resolved by version. The script's report goes
    # here and not in the base: it belongs to this version's run.
    out_dir: Path
    # De donde salio este corpus. En el manifiesto y en el reporte, porque un
    # corpus sin procedencia no se puede rastrear.
    # || Where this corpus came from. In the manifest and in the report, because
    # a corpus with no provenance cannot be traced.
    source: str
    tenant_id: str
    doc_version: str
    modules: int
    files: int
    documents: int
    chunks: int
    tokens: int
    zero_chunk_files: list[dict] = field(default_factory=list)
    failed_files: list[dict] = field(default_factory=list)
    per_module: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        """JSON-safe, for the job row. || Serializable, para la fila del job."""
        return {**asdict(self), "out_dir": str(self.out_dir)}


@dataclass
class EmbedStepResult:
    # Donde escribio de verdad, resuelto por version.
    # || Where it actually wrote, resolved by version.
    out_dir: Path
    modules: int
    to_embed: int
    reused: int
    duplicates_saved: int
    tokens_billed: int
    batches: int
    estimated_cost_usd: float
    embedded: int = 0
    rows_written: int = 0
    dropped: int = 0
    failed_batches: int = 0
    per_module: list[dict] = field(default_factory=list)
    # The runner's ModuleResult objects, for the console report. Kept out of
    # `summary()` because they are not JSON and the job row is JSONB.
    # || Los objetos ModuleResult del runner, para el reporte de consola. Fuera
    # de `summary()` porque no son JSON y la fila del job es JSONB.
    module_results: list = field(default_factory=list, repr=False)
    # The manifest this run wrote, for the console report.
    # || El manifiesto que escribio esta corrida, para el reporte de consola.
    manifest: object | None = field(default=None, repr=False)

    def summary(self) -> dict:
        """JSON-safe, for the job row. || Serializable, para la fila del job."""
        return {
            key: (str(value) if key == "out_dir" else value)
            for key, value in asdict(self).items()
            if key not in ("module_results", "manifest")
        }


@dataclass
class LoadStepResult:
    corpus_id: str
    # De donde leyo, resuelto por version.
    # || Where it read from, resolved by version.
    chunks_dir: Path
    tenant_id: str
    doc_version: str
    modules: int
    rows_ready: int
    distinct_texts: int
    chunks_without_vector: int
    rows_written: int = 0
    pruned: int = 0
    per_module: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        """JSON-safe, for the job row. || Serializable, para la fila del job."""
        return {**asdict(self), "chunks_dir": str(self.chunks_dir)}


@dataclass
class ResetStepResult:
    deleted_chunks: int
    deleted_edges: int
    deleted_versions: int


# --- Trocear || Chunk ----------------------------------------------------------


def chunk_corpus(
    *,
    source: CorpusSource,
    out_dir: Path,
    modules: list[str] | None = None,
    tenant_id: str | None = None,
    doc_version: str | None = None,
    progress: Progress = _silent,
) -> ChunkStepResult:
    """Chunk every module of ``source`` into ``out_dir``, and write the manifest.

    || Trocea cada módulo de ``source`` a ``out_dir``, y escribe el manifiesto.
    """
    settings = get_settings()
    tenant_id = tenant_id or settings.TENANT_ID
    doc_version = doc_version or settings.DOC_VERSION

    # Cada version tiene su directorio. Ver `corpus_dir`.
    # || Each version gets its own directory. See `corpus_dir`.
    out_dir = corpus_dir(out_dir, doc_version)
    out_dir.mkdir(parents=True, exist_ok=True)
    discovered = source.modules()
    if modules:
        wanted = set(modules)
        discovered = {name: keys for name, keys in discovered.items() if name in wanted}
    if not discovered:
        raise FileNotFoundError(
            f"No module found in {source.label()}. "
            f"|| No se encontró ningún módulo en {source.label()}."
        )

    # A module removed from the source leaves an ORPHANED <module>.json under
    # this version's directory: this function only WRITES the modules it finds,
    # it never deletes one that vanished. `embed_corpus` and `load_corpus` then
    # `module_files()`-glob every `*.json` in the directory, with no way to tell
    # a fresh file from a leftover -- so a module that used to be chunked from a
    # local root and later moved to a bucket that does not have it gets loaded
    # into Postgres anyway, silently, sourced from stale disk state instead of
    # the configured source.
    #
    # Demonstrated: switching this project's own corpus from a 28-module local
    # root to a 24-module bucket left 4 stale module files behind
    # (`civil_liability.json`, `financing.json`, `machinery.json`,
    # `surety_bonds.json`), and the next `embed` + `load` run picked all 28 up --
    # 24 documents from data the current source no longer has ended up in
    # Railway's database.
    #
    # Only on a FULL run (``modules`` unset): a filtered run (``--module
    # policies``) legitimately leaves its siblings untouched, and deleting them
    # would destroy modules that are still valid.
    # || Un módulo que se saca de la fuente deja un `<módulo>.json` HUÉRFANO bajo
    # el directorio de esta versión: esta función solo ESCRIBE los módulos que
    # encuentra, nunca borra uno que desapareció. `embed_corpus` y `load_corpus`
    # después hacen `module_files()` -glob de todo `*.json` del directorio, sin
    # forma de distinguir un archivo fresco de uno que sobró -- así que un módulo
    # que se troceaba de una raíz local y después se movió a un bucket que no lo
    # tiene se carga en Postgres igual, en silencio, con datos viejos de disco en
    # lugar de la fuente configurada.
    #
    # Demostrado: cambiar el corpus de este proyecto de una raíz local de 28
    # módulos a un bucket de 24 dejó 4 archivos huérfanos
    # (`civil_liability.json`, `financing.json`, `machinery.json`,
    # `surety_bonds.json`), y la siguiente corrida de `embed` + `load` los
    # levantó los 28 — 24 documentos de datos que la fuente actual ya no tiene
    # terminaron en la base de Railway.
    #
    # Solo en una corrida COMPLETA (``modules`` sin poner): una corrida filtrada
    # (``--module policies``) deja legítimamente sus hermanos sin tocar, y
    # borrarlos destruiría módulos que siguen siendo válidos.
    if not modules:
        orphaned = sorted(
            path.stem
            for path in out_dir.glob("*.json")
            if path.name != MANIFEST_FILENAME and path.stem not in discovered
        )
        for stale in orphaned:
            (out_dir / f"{stale}.json").unlink()
        if orphaned:
            logger.warning(
                "removed_orphaned_module_files",
                out_dir=str(out_dir),
                modules=orphaned,
            )

    # Built through the composition root so the batch run and the HTTP API share
    # one configuration -- including the WINDOWS navigation tree. Constructing
    # the chunker directly once left the breadcrumb unresolved for the whole
    # corpus, silently.
    # || Se construye por la raíz de composición así la corrida batch y la API
    # comparten una única configuración — incluido el árbol de WINDOWS.
    # Construirlo directo una vez dejó el breadcrumb sin resolver en todo el
    # corpus, en silencio.
    if tenant_id != settings.TENANT_ID or doc_version != settings.DOC_VERSION:
        from app.generation.rag.chunking.functional_spec import FunctionalSpecChunker
        from app.generation.rag.navigation import get_navigation_tree

        chunker = FunctionalSpecChunker(
            narrative_token_cap=settings.NARRATIVE_CHUNK_TOKEN_CAP,
            index_doc_min_links=settings.INDEX_DOC_MIN_LINKS,
            index_doc_min_link_density=settings.INDEX_DOC_MIN_LINK_DENSITY,
            navigation_tree=get_navigation_tree(settings.WINDOWS_TREE_PATH),
            tenant_id=tenant_id,
            doc_version=doc_version,
        )
    else:
        from app.dependencies import get_functional_spec_chunker

        chunker = get_functional_spec_chunker()

    result = ChunkStepResult(
        corpus_id=str(uuid.uuid4()),
        out_dir=out_dir,
        source=source.label(),
        tenant_id=tenant_id,
        doc_version=doc_version,
        modules=len(discovered),
        files=0,
        documents=0,
        chunks=0,
        tokens=0,
    )

    for module, keys in discovered.items():
        documents, zero_chunk_files, failed_files = chunk_module(chunker, source, module, keys)

        module_chunks = sum(len(d["chunks"]) for d in documents)
        module_tokens = sum(c["token_count"] for d in documents for c in d["chunks"])
        (out_dir / f"{module}.json").write_text(
            json.dumps({"module": module, "documents": documents}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        result.files += len(keys)
        result.documents += len(documents)
        result.chunks += module_chunks
        result.tokens += module_tokens
        result.zero_chunk_files.extend(zero_chunk_files)
        result.failed_files.extend(failed_files)
        result.per_module.append(
            {
                "module": module,
                "files": len(keys),
                "documents": len(documents),
                "chunks": module_chunks,
                "tokens": module_tokens,
                "table": sum(
                    1
                    for d in documents
                    for c in d["chunks"]
                    if c["metadata"]["chunk_type"] == "table"
                ),
                "narrative": sum(
                    1
                    for d in documents
                    for c in d["chunks"]
                    if c["metadata"]["chunk_type"] == "narrative"
                ),
                "zero_chunks": len(zero_chunk_files),
                "failed": len(failed_files),
            }
        )
        progress(
            step="chunk",
            module=module,
            files=len(keys),
            chunks=module_chunks,
            done=len(result.per_module),
            total=result.modules,
        )

    # The manifest is the authoritative declaration of which run produced this
    # corpus. Without it the per-module JSONs are a pile of chunks with no
    # provenance, and the load step refuses to guess.
    # || El manifiesto es la declaración autoritativa de qué corrida produjo este
    # corpus. Sin él los JSON por módulo son una pila de chunks sin procedencia, y
    # el paso de carga se niega a adivinar.
    manifest = CorpusManifest(
        corpus_id=result.corpus_id,
        tenant_id=tenant_id,
        doc_version=doc_version,
        generated_at=datetime.now(UTC),
        source_root=source.label(),
        modules=sorted(discovered),
        total_documents=result.documents,
        total_chunks=result.chunks,
        total_tokens=result.tokens,
    )
    (out_dir / MANIFEST_FILENAME).write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    return result


# --- Embeber || Embed ----------------------------------------------------------


def embed_corpus(
    *,
    chunks_dir: Path,
    out_dir: Path | None = None,
    modules: list[str] | None = None,
    dry_run: bool = False,
    progress: Progress = _silent,
) -> EmbedStepResult:
    """Embed what has no vector yet, reusing by ``content_hash``.

    Everything is planned BEFORE the first call, so a ``dry_run`` is a real
    preview and a chunk over the model's input cap is reported before paying for
    anything.

    || Embebe lo que todavía no tiene vector, reusando por ``content_hash``. Todo
    se planifica ANTES de la primera llamada, así un ``dry_run`` es una vista
    previa real y un chunk que pasa el tope de entrada del modelo se reporta antes
    de pagar nada.
    """
    from app.generation.rag.embedding.runner import (
        embed_module,
        estimated_cost_usd,
        load_module_chunks,
        plan_module,
        verify_before_embedding,
        verify_module_on_disk,
    )
    from app.generation.rag.embedding.sidecar import load_sidecar

    settings = get_settings()
    chunks_dir = corpus_dir(chunks_dir, settings.DOC_VERSION)
    out_dir = corpus_dir(out_dir or settings.EMBEDDINGS_PATH, settings.DOC_VERSION)

    paths = module_files(chunks_dir)
    if modules:
        wanted = set(modules)
        paths = [path for path in paths if path.stem in wanted]
    if not paths:
        raise FileNotFoundError(
            f"No module JSON found under {chunks_dir}. "
            f"|| No se encontró ningún JSON de módulo bajo {chunks_dir}."
        )

    plans = []
    for path in paths:
        module, chunks = load_module_chunks(path)
        verify_before_embedding(chunks, max_input_tokens=settings.EMBEDDING_MAX_INPUT_TOKENS)
        _, existing_index = load_sidecar(out_dir, module)
        plans.append((module, chunks, plan_module(module, chunks, existing_index)))

    tokens = sum(plan.tokens_to_bill for _, _, plan in plans)
    result = EmbedStepResult(
        out_dir=out_dir,
        modules=len(plans),
        to_embed=sum(len(plan.to_embed) for _, _, plan in plans),
        reused=sum(plan.reused for _, _, plan in plans),
        duplicates_saved=sum(plan.duplicates_saved for _, _, plan in plans),
        tokens_billed=tokens,
        batches=sum(plan.batches(settings.EMBEDDING_BATCH_SIZE) for _, _, plan in plans),
        estimated_cost_usd=estimated_cost_usd(tokens),
    )
    progress(step="embed", phase="planned", to_embed=result.to_embed, tokens=tokens)

    if dry_run or result.to_embed == 0:
        return result

    # Imported here so a dry run never needs an API key.
    # || Se importa acá para que una corrida en seco nunca necesite una clave.
    from app.dependencies import get_embedder

    embedder = get_embedder()
    for module, chunks, plan in plans:
        existing_vectors, existing_index = load_sidecar(out_dir, module)
        module_result = embed_module(
            plan,
            embedder=embedder,
            root=out_dir,
            existing_vectors=existing_vectors,
            existing_index=existing_index,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            checkpoint_every=settings.EMBEDDING_CHECKPOINT_EVERY,
        )
        verify_module_on_disk(
            out_dir,
            module,
            dimensions=embedder.dimensions,
            corpus_hashes={chunk.content_hash for chunk in chunks},
        )
        result.embedded += module_result.embedded
        result.rows_written += module_result.rows_written
        result.dropped += module_result.dropped
        result.failed_batches += len(module_result.failed)
        result.module_results.append(module_result)
        result.per_module.append(
            {
                "module": module,
                "embedded": module_result.embedded,
                "rows": module_result.rows_written,
                "reused": module_result.reused,
                "failed_batches": len(module_result.failed),
            }
        )
        progress(
            step="embed",
            module=module,
            embedded=module_result.embedded,
            done=len(result.per_module),
            total=result.modules,
        )

    # The sidecar's manifest is written HERE and not in the script, because the
    # endpoint runs the same step and a run that embeds without leaving its
    # authoritative record is a run nobody can audit afterwards. Moving the
    # orchestration without moving this would have been exactly the silent
    # divergence the extraction exists to prevent.
    # || El manifiesto del sidecar se escribe ACA y no en el script, porque el
    # endpoint corre el mismo paso y una corrida que embebe sin dejar su
    # registro autoritativo es una corrida que despues nadie puede auditar.
    # Mover la orquestacion sin mover esto habria sido justamente la divergencia
    # silenciosa que la extraccion existe para evitar.
    corpus_id, tenant_id, doc_version = corpus_identity(chunks_dir)
    manifest = EmbeddingManifest(
        corpus_id=corpus_id,
        tenant_id=tenant_id,
        doc_version=doc_version,
        model=embedder.model,
        dimensions=embedder.dimensions,
        generated_at=datetime.now(UTC).isoformat(),
        total_rows=result.rows_written,
        embedded_now=result.embedded,
        reused=sum(r.reused for r in result.module_results),
        dropped=result.dropped,
        tokens_billed=sum(r.tokens_billed for r in result.module_results),
        failed_batches=[batch for r in result.module_results for batch in r.failed],
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / EMBEDDING_MANIFEST_FILENAME).write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    result.manifest = manifest
    return result


# --- Cargar || Load ------------------------------------------------------------


def load_corpus(
    *,
    chunks_dir: Path,
    embeddings_dir: Path | None = None,
    modules: list[str] | None = None,
    prune: bool = False,
    dry_run: bool = False,
    progress: Progress = _silent,
) -> LoadStepResult:
    """``COPY`` the corpus and its vectors into Postgres.

    ``prune`` is only valid on a FULL run: it deletes the rows whose text is no
    longer anywhere in the corpus, and a partial corpus would make it delete
    real rows. Measured once on a single module: it would have deleted 27 of the
    28 modules.

    || ``COPY`` del corpus y sus vectores a Postgres. ``prune`` solo vale en una
    corrida COMPLETA: borra las filas cuyo texto ya no está en ninguna parte del
    corpus, y un corpus parcial lo haría borrar filas reales. Medido una vez
    sobre un solo módulo: habría borrado 27 de los 28.
    """
    from app.generation.rag.store.loader import iter_rows, load_module, prune_corpus

    settings = get_settings()
    chunks_dir = corpus_dir(chunks_dir, settings.DOC_VERSION)
    embeddings_dir = corpus_dir(
        embeddings_dir or settings.EMBEDDINGS_PATH, settings.DOC_VERSION
    )

    paths = module_files(chunks_dir)
    if modules:
        wanted = set(modules)
        paths = [path for path in paths if path.stem in wanted]
        if prune:
            raise ValueError(
                "--prune with a module filter would delete the other modules' rows. "
                "|| --prune con un filtro de módulos borraría las filas de los demás."
            )
    if not paths:
        raise FileNotFoundError(
            f"No module JSON found under {chunks_dir}. "
            f"|| No se encontró ningún JSON de módulo bajo {chunks_dir}."
        )

    corpus_id, tenant_id, doc_version = corpus_identity(chunks_dir)

    # Everything is read and joined first, so a dry run is a real preview and a
    # missing sidecar is reported before any connection is opened.
    # || Se lee y se une todo primero, así una corrida en seco es una vista
    # previa real y un sidecar faltante se reporta antes de abrir conexiones.
    prepared, corpus_hashes = [], set()
    result = LoadStepResult(
        corpus_id=corpus_id,
        chunks_dir=chunks_dir,
        tenant_id=tenant_id,
        doc_version=doc_version,
        modules=len(paths),
        rows_ready=0,
        distinct_texts=0,
        chunks_without_vector=0,
    )
    for path in paths:
        module, rows, without_vector = iter_rows(path, embeddings_dir)
        prepared.append((module, rows, without_vector))
        result.rows_ready += len(rows)
        result.chunks_without_vector += len(without_vector)
        corpus_hashes.update(row[2] for row in rows)
    result.distinct_texts = len(corpus_hashes)
    progress(step="load", phase="prepared", rows_ready=result.rows_ready)

    if dry_run:
        return result

    # Imported here so a dry run never needs a reachable database.
    # || Se importa acá para que una corrida en seco nunca necesite base.
    from app.foundation.persistence.database import get_engine

    with get_engine().raw_connection().driver_connection as connection:
        for module, rows, without_vector in prepared:
            copied, written = load_module(
                connection, rows, dimensions=settings.EMBEDDING_DIMENSIONS
            )
            connection.commit()
            result.rows_written += written
            result.per_module.append(
                {
                    "module": module,
                    "copied": copied,
                    "written": written,
                    "without_vector": len(without_vector),
                }
            )
            progress(
                step="load",
                module=module,
                written=written,
                without_vector=len(without_vector),
                done=len(result.per_module),
                total=result.modules,
            )
        if prune:
            result.pruned = prune_corpus(connection, tenant_id, doc_version, corpus_hashes)
            connection.commit()
            progress(step="load", phase="pruned", pruned=result.pruned)
    return result


# --- Vaciar || Reset -----------------------------------------------------------


def reset_corpus(*, tenant_id: str, doc_version: str, progress: Progress = _silent) -> ResetStepResult:
    """Delete EVERY row of one corpus. Destructive and not undoable.

    Scoped to one ``(tenant_id, doc_version)`` and never to the whole table: a
    truncate would take other clients' corpora with it. The caller is
    responsible for having confirmed the identity -- see the endpoint, which
    requires it spelled out rather than a boolean flag.

    || Borra TODAS las filas de un corpus. Destructivo y sin vuelta atrás.
    Alcance de un solo ``(tenant_id, doc_version)`` y nunca de la tabla entera:
    un truncate se llevaría los corpus de otros clientes. Quien llama es
    responsable de haber confirmado la identidad — ver el endpoint, que la pide
    escrita en lugar de un booleano.
    """
    from sqlalchemy import text

    from app.foundation.persistence.database import get_engine

    statements = (
        ("chunks", "DELETE FROM chunks WHERE tenant_id = :t AND doc_version = :v"),
        (
            "process_map_edges",
            "DELETE FROM process_map_edges WHERE tenant_id = :t AND doc_version = :v",
        ),
        (
            "corpus_versions",
            "DELETE FROM corpus_versions WHERE tenant_id = :t AND doc_version = :v",
        ),
    )
    deleted: dict[str, int] = {}
    with get_engine().begin() as connection:
        for table, statement in statements:
            deleted[table] = connection.execute(
                text(statement), {"t": tenant_id, "v": doc_version}
            ).rowcount
            progress(step="reset", table=table, deleted=deleted[table])
    logger.warning(
        "corpus_reset", tenant_id=tenant_id, doc_version=doc_version, deleted=deleted
    )
    return ResetStepResult(
        deleted_chunks=deleted["chunks"],
        deleted_edges=deleted["process_map_edges"],
        deleted_versions=deleted["corpus_versions"],
    )

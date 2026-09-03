"""POST /documents/ingest and POST /documents/ingest-file.

Thin router: normalizes + chunks the document and returns the chunks. No
embeddings, no persistence — those are separate layers not built yet
(``generation/rag/embedding/`` and a store, per the course architecture).

Two entry points, same underlying logic (``_ingest``):

* ``/ingest`` — JSON body with ``content`` already read as text. Meant for
  programmatic callers (e.g. the business backend) that already have the
  document text in hand.
* ``/ingest-file`` — multipart file upload. Meant for manually testing from
  Swagger UI, which renders a native "Choose File" button for
  ``UploadFile`` params (a JSON string field has no such button, and a raw
  markdown file is impractical to paste/escape by hand into a JSON body).

|| Router delgado: normaliza + trocea el documento y devuelve los chunks.
Sin embeddings, sin persistencia — esas son capas separadas todavía no
construidas (``generation/rag/embedding/`` y un store, según la
arquitectura del curso).

Dos puntos de entrada, misma lógica de base (``_ingest``):

* ``/ingest`` — body JSON con ``content`` ya leído como texto. Pensado para
  llamadores programáticos (ej. el backend de negocio) que ya tienen el
  texto del documento en mano.
* ``/ingest-file`` — subida de archivo multipart. Pensado para probar a
  mano desde Swagger UI, que renderiza un botón nativo "Choose File" para
  parámetros ``UploadFile`` (un campo string JSON no tiene ese botón, y
  pegar/escapar a mano un markdown crudo en un body JSON es poco práctico).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.dependencies import get_functional_spec_chunker
from app.generation.rag.chunking.functional_spec import FunctionalSpecChunker
from app.generation.rag.schemas import IngestRequest, IngestResponse, IngestStats

log = structlog.get_logger()

router = APIRouter(prefix="/documents", tags=["documents"])


def _ingest(*, filename: str, content: str, chunker: FunctionalSpecChunker) -> IngestResponse:
    """Shared body for both endpoints below. || Cuerpo compartido de los dos endpoints de abajo."""
    log.info("documents_ingest_received", filename=filename)
    try:
        documents = chunker.chunk(filename, content)
    except Exception as exc:  # malformed input becomes a 500. || entrada malformada se vuelve un 500.
        log.error(
            "documents_ingest_failed",
            filename=filename,
            error_type=type(exc).__name__,
            error=str(exc)[:300],
        )
        raise HTTPException(status_code=500, detail="Failed to chunk document.") from exc

    chunks = [chunk for document in documents for chunk in document.chunks]
    stats = IngestStats(
        total_documents=len(documents),
        total_chunks=len(chunks),
        total_tokens=sum(c.token_count for c in chunks),
        table_chunks=sum(1 for c in chunks if c.metadata.chunk_type == "table"),
        narrative_chunks=sum(1 for c in chunks if c.metadata.chunk_type == "narrative"),
    )
    log.info(
        "documents_ingest_done",
        filename=filename,
        document_ids=[d.document_id for d in documents],
        **stats.model_dump(),
    )
    return IngestResponse(source_file=filename, documents=documents, stats=stats)


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: IngestRequest,
    chunker: FunctionalSpecChunker = Depends(get_functional_spec_chunker),  # noqa: B008 — FastAPI's required DI idiom.
) -> IngestResponse:
    """Parse one functional-spec markdown document into chunks (no embeddings).

    ``content`` must be the raw markdown TEXT, not a file path — the service
    never reads from disk.

    || Parsea un documento markdown de especificación funcional en chunks
    (sin embeddings). ``content`` debe ser el TEXTO markdown crudo, no una
    ruta de archivo — el servicio nunca lee del disco.
    """
    return _ingest(filename=request.filename, content=request.content, chunker=chunker)


@router.post("/ingest-file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(  # noqa: B008 — FastAPI's required DI idiom.
        ..., description="Raw .md file, e.g. ca014.md. || Archivo .md crudo, ej. ca014.md."
    ),
    chunker: FunctionalSpecChunker = Depends(get_functional_spec_chunker),  # noqa: B008
) -> IngestResponse:
    """Same as ``/ingest``, but takes a file upload instead of a JSON body —
    convenient for testing by hand from Swagger UI ("Choose File" button).

    || Igual que ``/ingest``, pero recibe un archivo subido en vez de un
    body JSON — cómodo para probar a mano desde Swagger UI (botón "Choose File").
    """
    raw_bytes = await file.read()
    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded markdown.") from exc
    return _ingest(filename=file.filename or "document.md", content=content, chunker=chunker)

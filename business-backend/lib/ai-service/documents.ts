import "server-only";

import { postFormData } from "./base-client";
import type { IngestResponse } from "./types";

/** Single-document ingestion context. Never imports another context. || Contexto de ingesta puntual. Nunca importa otro contexto. */

/** Chunking a long document is deterministic and local, but not instant. || Trocear un documento largo es determinístico y local, pero no instantáneo. */
const INGEST_TIMEOUT_MS = 60_000;

/**
 * Chunks one document and returns the result WITHOUT persisting it.
 * That is the endpoint's contract, not a choice this layer makes -- there is no
 * "save" call to pair with it.
 *
 * || Trocea un documento y devuelve el resultado SIN persistirlo. Es el
 * contrato del endpoint, no una decisión de esta capa -- no existe una llamada
 * de "guardar" que la acompañe.
 */
export function ingestFile(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);
  return postFormData<IngestResponse>(
    "/documents/ingest-file",
    form,
    INGEST_TIMEOUT_MS,
  );
}

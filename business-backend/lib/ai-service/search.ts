import "server-only";

import { getJson } from "./base-client";
import type { SearchParams, SearchResponse } from "./types";

/** Retrieval context. Never imports another context. || Contexto de recuperación. Nunca importa otro contexto. */

/**
 * The reranker costs 3x the latency (measured, see the endpoint's own docs), so
 * this call gets a longer leash than the default.
 * || El reranker cuesta 3 veces la latencia (medido, ver la doc del endpoint),
 * así que esta llamada tiene más margen que el default.
 */
const SEARCH_TIMEOUT_MS = 60_000;

export function search(params: SearchParams): Promise<SearchResponse> {
  return getJson<SearchResponse>(
    "/search",
    {
      q: params.q,
      limit: params.limit,
      max_per_document: params.max_per_document,
      module_code: params.module_code,
      window_type_name: params.window_type_name,
      lexical: params.lexical,
      split: params.split,
      rerank: params.rerank,
    },
    SEARCH_TIMEOUT_MS,
  );
}

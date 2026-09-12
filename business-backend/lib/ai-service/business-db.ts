import "server-only";

import { getJson, postJson } from "./base-client";
import type {
  ActivateRunRequest,
  ActivateRunResponse,
  ExtractionRunList,
  TableDictionaryDetail,
} from "./types";

/** Mirror run selection context. Never imports another context.
 * || Contexto de selección de corrida del mirror. Nunca importa otro contexto.
 */

export function listRuns(): Promise<ExtractionRunList> {
  return getJson<ExtractionRunList>("/business-db/runs");
}

export function activateRun(
  runId: string,
  body?: ActivateRunRequest,
): Promise<ActivateRunResponse> {
  return postJson<ActivateRunResponse>(
    `/business-db/runs/${encodeURIComponent(runId)}/activate`,
    body ?? {},
  );
}

/**
 * Everything the ACTIVE run declares about one table.
 *
 * Read on demand and never inlined in a prompt: twelve tables in this shape
 * measured 15,969 tokens against a 16,384-token context ceiling. What the
 * answer carries is the description; the columns are fetched when asked for.
 *
 * || Todo lo que declara la corrida activa sobre una tabla. Se lee a demanda y
 * nunca viaja en un prompt: 12 tablas así midieron 15.969 tokens.
 */
export function getTableDictionary(
  tableName: string,
): Promise<TableDictionaryDetail> {
  return getJson<TableDictionaryDetail>(
    `/business-db/tables/${encodeURIComponent(tableName)}`,
  );
}

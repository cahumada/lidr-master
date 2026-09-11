import "server-only";

import { getJson, postJson } from "./base-client";
import type {
  ActivateRunRequest,
  ActivateRunResponse,
  ExtractionRunList,
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

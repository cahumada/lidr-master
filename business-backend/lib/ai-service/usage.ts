import "server-only";

import { getJson } from "./base-client";
import type { UsageSummary } from "./types";

/** Usage ledger context. Never imports another context.
 * || Contexto del ledger de usage. Nunca importa otro contexto.
 */

export type UsageSummaryQuery = {
  from?: string;
  to?: string;
  session_id?: string;
  purpose?: string;
};

/**
 * Tenant totals. Query keys travel as-is (`from` / `to`); range checks
 * live on the service.
 * || Totales del tenant. Las claves viajan tal cual (`from` / `to`); el
 * rango lo valida el servicio.
 */
export function getUsageSummary(
  params?: UsageSummaryQuery,
): Promise<UsageSummary> {
  return getJson<UsageSummary>("/usage/summary", params);
}

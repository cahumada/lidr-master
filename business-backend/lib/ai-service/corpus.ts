import "server-only";

import { getJson, postJson } from "./base-client";
import type {
  CorpusIdentity,
  IngestionJob,
  RebuildRequest,
  RebuildStarted,
} from "./types";

/** Corpus rebuild context. Never imports another context. || Contexto de reconstrucción del corpus. Nunca importa otro contexto. */

export function startRebuild(request: RebuildRequest): Promise<RebuildStarted> {
  return postJson<RebuildStarted>("/corpus/rebuild", request);
}

export function job(id: string): Promise<IngestionJob> {
  return getJson<IngestionJob>(`/corpus/jobs/${encodeURIComponent(id)}`);
}

export function jobs(limit = 20): Promise<IngestionJob[]> {
  return getJson<IngestionJob[]>("/corpus/jobs", { limit });
}

/**
 * The corpus identity a `reset` must be confirmed against.
 *
 * Read from the most recent job, because every job row carries the
 * `tenant_id` / `doc_version` the service was configured with when it ran. The
 * service exposes no settings endpoint, and the alternative -- a constant in
 * this UI -- would go stale and quietly turn the confirmation into a formality.
 *
 * Returns `null` when there is no job yet: with nothing to confirm against, the
 * screen keeps `reset` disabled rather than inventing a value.
 *
 * || La identidad del corpus contra la que hay que confirmar un `reset`. Se lee
 * del job más reciente, porque cada fila de job lleva el `tenant_id` /
 * `doc_version` con el que el servicio estaba configurado cuando corrió. El
 * servicio no expone un endpoint de configuración, y la alternativa -- una
 * constante en esta UI -- se desactualizaría y convertiría la confirmación en
 * un trámite.
 *
 * Devuelve `null` cuando todavía no hay ningún job: sin nada contra qué
 * confirmar, la pantalla deja `reset` deshabilitado en vez de inventar un valor.
 */
export async function corpusIdentity(): Promise<CorpusIdentity | null> {
  const recent = await jobs(1);
  const last = recent[0];
  if (!last) return null;
  return { tenant_id: last.tenant_id, doc_version: last.doc_version };
}

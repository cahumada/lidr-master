import "server-only";

import { getJson, postJson, postJsonAllowingStatuses } from "./base-client";
import type {
  AnswerAgenticCompleted,
  AnswerAgenticProgress,
  AnswerAgenticResponse,
  AnswerAgenticResumeRequest,
  AnswerAgenticStart,
  AnswerRequest,
} from "./types";

/** Answer and agentic-answer context. Never imports another context.
 * || Contexto de respuesta y respuesta agentica. Nunca importa otro contexto.
 */

/**
 * The agentic graph may call retrieval, an LLM, and pause for human review —
 * longer leash than search alone.
 * || El grafo agentico puede recuperar, llamar al LLM y pausar para revisión
 * humana — más margen que la búsqueda sola.
 */
const AGENTIC_TIMEOUT_MS = 120_000;

export function answerAgentic(
  body: AnswerRequest,
): Promise<{ status: number; data: AnswerAgenticResponse }> {
  return postJsonAllowingStatuses<AnswerAgenticResponse>(
    "/answer/agentic",
    body,
    [200, 202],
    AGENTIC_TIMEOUT_MS,
  );
}

export function answerAgenticResume(
  body: AnswerAgenticResumeRequest,
): Promise<AnswerAgenticCompleted> {
  return postJson<AnswerAgenticCompleted>(
    "/answer/agentic/resume",
    body,
    AGENTIC_TIMEOUT_MS,
  );
}

/**
 * Schedules the graph in the background and returns at once — the caller
 * polls `answerAgenticProgress` to watch the agents work.
 * || Agenda el grafo en background y vuelve al instante — quien llama
 * consulta `answerAgenticProgress` para ver a los agentes trabajar.
 */
export function answerAgenticStart(
  body: AnswerRequest,
): Promise<AnswerAgenticStart> {
  return postJson<AnswerAgenticStart>("/answer/agentic/start", body);
}

export function answerAgenticProgress(
  threadId: string,
): Promise<AnswerAgenticProgress> {
  return getJson<AnswerAgenticProgress>(
    `/answer/agentic/${encodeURIComponent(threadId)}/progress`,
  );
}

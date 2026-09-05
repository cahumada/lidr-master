import "server-only";

import {
  deleteJson,
  deleteNoContent,
  getJson,
  postJson,
  postJsonAllowingStatuses,
} from "./base-client";
import type {
  AnswerAgenticCompleted,
  AnswerAgenticProgress,
  AnswerAgenticResponse,
  AnswerAgenticResumeRequest,
  AnswerAgenticStart,
  AnswerRequest,
  SessionCreated,
  SessionView,
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

/**
 * Conversation sessions. The id is issued by the service and sent back on
 * every turn; without one, a turn is answered with no memory.
 * || Sesiones de conversación. El id lo emite el servicio y se manda en cada
 * turno; sin él, el turno se responde sin memoria.
 */
export function createAnswerSession(): Promise<SessionCreated> {
  return postJson<SessionCreated>("/answer/session", {});
}

export function readAnswerSession(sessionId: string): Promise<SessionView> {
  return getJson<SessionView>(`/answer/session/${encodeURIComponent(sessionId)}`);
}

/**
 * Idempotent on the service side: discarding a thread must not be able to
 * fail because the session had already expired.
 * || Idempotente del lado del servicio: descartar un hilo no puede fallar
 * porque la sesión ya hubiera vencido.
 */
export function deleteAnswerSession(sessionId: string): Promise<void> {
  return deleteNoContent(`/answer/session/${encodeURIComponent(sessionId)}`);
}

export function unpinAnswerSessionAnchor(
  sessionId: string,
  kind: string,
  value: string,
): Promise<SessionView> {
  return deleteJson<SessionView>(
    `/answer/session/${encodeURIComponent(sessionId)}/anchors/${encodeURIComponent(kind)}/${encodeURIComponent(value)}`,
  );
}

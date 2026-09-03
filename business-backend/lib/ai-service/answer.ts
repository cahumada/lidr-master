import "server-only";

import { postJson, postJsonAllowingStatuses } from "./base-client";
import type {
  AnswerAgenticCompleted,
  AnswerAgenticResponse,
  AnswerAgenticResumeRequest,
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

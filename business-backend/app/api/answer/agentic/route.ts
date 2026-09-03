import { toErrorPayload } from "@/lib/ai-service/base-client";
import { answerAgentic } from "@/lib/ai-service/answer";
import type { AnswerRequest } from "@/lib/ai-service/types";

/**
 * `POST /api/answer/agentic` — relay to `POST /answer/agentic`.
 * || Relay hacia `POST /answer/agentic`.
 *
 * Forwards 200 and 202 as-is: 202 is a deliberate human-review pause, not an
 * error.
 * || Reenvía 200 y 202 tal cual: 202 es una pausa deliberada, no un error.
 */
export async function POST(request: Request) {
  let body: AnswerRequest;
  try {
    body = (await request.json()) as AnswerRequest;
  } catch {
    return Response.json(
      { error: "Cuerpo JSON inválido.", status: 400 },
      { status: 400 },
    );
  }

  if (!body.question?.trim()) {
    return Response.json(
      { error: "Falta la pregunta.", status: 422 },
      { status: 422 },
    );
  }

  try {
    const result = await answerAgentic(body);
    return Response.json(result.data, { status: result.status });
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

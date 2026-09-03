import { toErrorPayload } from "@/lib/ai-service/base-client";
import { answerAgenticStart } from "@/lib/ai-service/answer";
import type { AnswerRequest } from "@/lib/ai-service/types";

/**
 * `POST /api/answer/agentic/start` — relay to `POST /answer/agentic/start`.
 * || Relay hacia `POST /answer/agentic/start`.
 *
 * Always 202: the service schedules the graph in the background and returns
 * a `thread_id` to poll, it never has an answer to give back here.
 * || Siempre 202: el servicio agenda el grafo en background y devuelve un
 * `thread_id` para consultar, nunca tiene una respuesta que devolver acá.
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
    const result = await answerAgenticStart(body);
    return Response.json(result, { status: 202 });
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

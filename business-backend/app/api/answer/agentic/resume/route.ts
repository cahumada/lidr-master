import { toErrorPayload } from "@/lib/ai-service/base-client";
import { answerAgenticResume } from "@/lib/ai-service/answer";
import type { AnswerAgenticResumeRequest } from "@/lib/ai-service/types";

/**
 * `POST /api/answer/agentic/resume` — relay to `POST /answer/agentic/resume`.
 * || Relay hacia `POST /answer/agentic/resume`.
 */
export async function POST(request: Request) {
  let body: AnswerAgenticResumeRequest;
  try {
    body = (await request.json()) as AnswerAgenticResumeRequest;
  } catch {
    return Response.json(
      { error: "Cuerpo JSON inválido.", status: 400 },
      { status: 400 },
    );
  }

  if (!body.thread_id?.trim()) {
    return Response.json(
      { error: "Falta el thread_id.", status: 422 },
      { status: 422 },
    );
  }

  try {
    const result = await answerAgenticResume(body);
    return Response.json(result);
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

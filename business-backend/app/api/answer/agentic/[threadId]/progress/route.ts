import { toErrorPayload } from "@/lib/ai-service/base-client";
import { answerAgenticProgress } from "@/lib/ai-service/answer";

/**
 * `GET /api/answer/agentic/[threadId]/progress` — relay to
 * `GET /answer/agentic/{thread_id}/progress`.
 * || Relay hacia `GET /answer/agentic/{thread_id}/progress`.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ threadId: string }> },
) {
  const { threadId } = await params;
  if (!threadId?.trim()) {
    return Response.json(
      { error: "Falta el thread_id.", status: 422 },
      { status: 422 },
    );
  }

  try {
    const result = await answerAgenticProgress(threadId);
    return Response.json(result);
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

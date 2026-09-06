import { deleteAnswerSession, readAnswerSession } from "@/lib/ai-service/answer";
import { toErrorPayload } from "@/lib/ai-service/base-client";

type Params = { params: Promise<{ sessionId: string }> };

/** `GET /api/answer/session/{id}` — what the conversation remembers.
 * || Lo que recuerda la conversación. */
export async function GET(_request: Request, { params }: Params) {
  const { sessionId } = await params;
  try {
    return Response.json(await readAnswerSession(sessionId));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

/** `DELETE /api/answer/session/{id}` — discard the conversation.
 * || Descarta la conversación. */
export async function DELETE(_request: Request, { params }: Params) {
  const { sessionId } = await params;
  try {
    await deleteAnswerSession(sessionId);
    return new Response(null, { status: 204 });
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

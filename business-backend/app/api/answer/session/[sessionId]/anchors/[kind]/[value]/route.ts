import { unpinAnswerSessionAnchor } from "@/lib/ai-service/answer";
import { toErrorPayload } from "@/lib/ai-service/base-client";

type Params = {
  params: Promise<{ sessionId: string; kind: string; value: string }>;
};

/** `DELETE /api/answer/session/{id}/anchors/{kind}/{value}` — unpin a constraint.
 * || Quita una restricción fijada. */
export async function DELETE(_request: Request, { params }: Params) {
  const { sessionId, kind, value } = await params;
  try {
    return Response.json(await unpinAnswerSessionAnchor(sessionId, kind, value));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

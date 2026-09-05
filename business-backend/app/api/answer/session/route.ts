import { createAnswerSession } from "@/lib/ai-service/answer";
import { toErrorPayload } from "@/lib/ai-service/base-client";

/**
 * `POST /api/answer/session` — relay to `POST /answer/session`.
 *
 * The id is minted by the service, never by the browser: an id the service
 * did not issue is an id it cannot validate, and it would let two tabs share
 * a conversation by accident.
 * || El id lo acuña el servicio, nunca el browser: un id que el servicio no
 * emitió es un id que no puede validar, y dejaría que dos pestañas compartan
 * una conversación por accidente.
 */
export async function POST() {
  try {
    return Response.json(await createAnswerSession(), { status: 201 });
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

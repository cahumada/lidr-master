import {
  deleteAnswerSession,
  readAnswerSession,
  renameAnswerSession,
} from "@/lib/ai-service/answer";
import { toErrorPayload } from "@/lib/ai-service/base-client";

type Params = { params: Promise<{ sessionId: string }> };

/** `GET /api/answer/session/{id}` — memory slots plus the durable transcript.
 * || Slots de memoria más el transcript. */
export async function GET(_request: Request, { params }: Params) {
  const { sessionId } = await params;
  try {
    return Response.json(await readAnswerSession(sessionId));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

/**
 * `PATCH /api/answer/session/{id}` — rename. Shape is checked here; empty
 * or over-long titles are the service's 422.
 * || Renombra. La forma se chequea acá; vacío o demasiado largo es 422
 * del servicio.
 */
export async function PATCH(request: Request, { params }: Params) {
  const { sessionId } = await params;

  let title: unknown;
  try {
    const body = (await request.json()) as { title?: unknown };
    title = body.title;
  } catch {
    return Response.json(
      { error: "Cuerpo JSON inválido.", status: 400 },
      { status: 400 },
    );
  }

  if (typeof title !== "string") {
    return Response.json(
      { error: "Falta el título.", status: 400 },
      { status: 400 },
    );
  }

  try {
    return Response.json(await renameAnswerSession(sessionId, title));
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

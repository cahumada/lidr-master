import { toErrorPayload } from "@/lib/ai-service/base-client";
import { getAnswerPrompt } from "@/lib/ai-service/answer";
import { requireAdmin } from "@/lib/auth/api-guards";

/**
 * `GET /api/answer/prompts/{id}` — relay to `GET /answer/prompts/{id}`.
 *
 * The role check comes FIRST and the AI service is not called until it passes.
 * `/answer` is not an admin screen, so hiding the link is presentation: this is
 * the protection. The prompt carries the persona, the guardrails and the
 * retrieved corpus in full.
 *
 * || El chequeo de rol va PRIMERO y el servicio IA no se llama hasta que pase.
 * `/answer` no es pantalla de administración: ocultar el link es presentación,
 * esto es la protección.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ promptId: string }> },
) {
  const refusal = await requireAdmin();
  if (refusal) return refusal;

  const { promptId } = await params;
  try {
    return Response.json(await getAnswerPrompt(promptId));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

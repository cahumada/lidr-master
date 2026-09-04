import { toErrorPayload } from "@/lib/ai-service/base-client";
import { createNamedProfile } from "@/lib/ai-service/config";
import type { NamedProfileWrite } from "@/lib/ai-service/types";

/**
 * `POST /api/config/agents/[agentKey]/profiles` — relay to the service.
 * || Relay hacia el servicio.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ agentKey: string }> },
) {
  const { agentKey } = await params;

  let body: NamedProfileWrite;
  try {
    body = (await request.json()) as NamedProfileWrite;
  } catch {
    return Response.json(
      { error: "Cuerpo JSON inválido.", status: 400 },
      { status: 400 },
    );
  }

  try {
    return Response.json(await createNamedProfile(agentKey, body));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

import { toErrorPayload } from "@/lib/ai-service/base-client";
import { deleteNamedProfile, updateNamedProfile } from "@/lib/ai-service/config";
import type { NamedProfileWrite } from "@/lib/ai-service/types";

/**
 * `PUT /api/config/agents/[agentKey]/profiles/[profileId]` — relay.
 * || Relay hacia el servicio.
 */
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ agentKey: string; profileId: string }> },
) {
  const { agentKey, profileId } = await params;

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
    return Response.json(await updateNamedProfile(agentKey, profileId, body));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

/**
 * `DELETE /api/config/agents/[agentKey]/profiles/[profileId]` — relay.
 * || Relay hacia el servicio.
 */
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ agentKey: string; profileId: string }> },
) {
  const { agentKey, profileId } = await params;

  try {
    return Response.json(await deleteNamedProfile(agentKey, profileId));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

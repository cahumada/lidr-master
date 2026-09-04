import { toErrorPayload } from "@/lib/ai-service/base-client";
import { deleteAgentProfile, updateAgentProfile } from "@/lib/ai-service/config";
import type { AgentProfileUpdate } from "@/lib/ai-service/types";

/**
 * `PUT /api/config/agents/[agentKey]` — relay to the service.
 * || Relay hacia el servicio.
 *
 * The service owns the validation (unknown agent, deterministic agent, model
 * outside the catalog, persona over the cap) and its 404/422 travel as-is:
 * duplicating those rules here would be a second place to keep in sync.
 * || El servicio es el dueño de la validación y sus 404/422 viajan tal cual:
 * duplicar esas reglas acá sería un segundo lugar que mantener sincronizado.
 */
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ agentKey: string }> },
) {
  const { agentKey } = await params;

  let body: AgentProfileUpdate;
  try {
    body = (await request.json()) as AgentProfileUpdate;
  } catch {
    return Response.json(
      { error: "Cuerpo JSON inválido.", status: 400 },
      { status: 400 },
    );
  }

  try {
    return Response.json(await updateAgentProfile(agentKey, body));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

/**
 * `DELETE /api/config/agents/[agentKey]` — drop the profile, back to defaults.
 * || Borra el perfil: el agente vuelve a los defaults del servicio.
 */
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ agentKey: string }> },
) {
  const { agentKey } = await params;

  try {
    return Response.json(await deleteAgentProfile(agentKey));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

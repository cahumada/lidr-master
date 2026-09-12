import { toErrorPayload } from "@/lib/ai-service/base-client";
import { getTableDictionary } from "@/lib/ai-service/business-db";

/**
 * `GET /api/business-db/tables/{name}` — relay to `GET /business-db/tables/{name}`.
 *
 * No role gate, deliberately: the business-db block is already shown in the
 * turn to any session, and this is more of the same authority. What stays
 * restricted is the full prompt, which carries the persona and the guardrails.
 *
 * || Sin gate de rol, a propósito: el bloque de base ya se le muestra a
 * cualquier sesión en el turno y esto es más de la misma autoridad. Lo que
 * sigue restringido es el prompt completo.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ name: string }> },
) {
  const { name } = await params;
  try {
    return Response.json(await getTableDictionary(name));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

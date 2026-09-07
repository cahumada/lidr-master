import type { NextRequest } from "next/server";

import { toErrorPayload } from "@/lib/ai-service/base-client";
import { getUsageSummary } from "@/lib/ai-service/usage";

/**
 * `GET /api/usage/summary` — relay to `GET /usage/summary`.
 *
 * `from`, `to`, `session_id` and `purpose` travel if the browser sent them.
 * The tenant is not accepted here: the service reads it from settings.
 * || Viajan si el browser los mandó. El tenant no se acepta: lo pone el
 * servicio.
 */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const from = params.get("from");
  const to = params.get("to");
  const sessionId = params.get("session_id");
  const purpose = params.get("purpose");

  try {
    return Response.json(
      await getUsageSummary({
        from: from || undefined,
        to: to || undefined,
        session_id: sessionId || undefined,
        purpose: purpose || undefined,
      }),
    );
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

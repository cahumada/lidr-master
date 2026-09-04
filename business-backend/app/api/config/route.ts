import { toErrorPayload } from "@/lib/ai-service/base-client";
import { serviceConfig } from "@/lib/ai-service/config";

/**
 * `GET /api/config` — relay to `GET /config`.
 * || Relay hacia `GET /config`.
 */
export async function GET() {
  try {
    return Response.json(await serviceConfig());
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

import { toErrorPayload } from "@/lib/ai-service/base-client";
import { listRuns } from "@/lib/ai-service/business-db";

/**
 * `GET /api/business-db/runs` — relay to `GET /business-db/runs`.
 * || Relay hacia `GET /business-db/runs`.
 */
export async function GET() {
  try {
    return Response.json(await listRuns());
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

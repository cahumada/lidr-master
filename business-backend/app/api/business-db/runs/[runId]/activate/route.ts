import { toErrorPayload } from "@/lib/ai-service/base-client";
import { activateRun } from "@/lib/ai-service/business-db";
import type { ActivateRunRequest } from "@/lib/ai-service/types";

/**
 * `POST /api/business-db/runs/[runId]/activate` — relay to
 * `POST /business-db/runs/{run_id}/activate`. The handler forwards the body
 * as-is and does not invent `activated_by`.
 * || Relay hacia `POST /business-db/runs/{run_id}/activate`. Reenvía el body
 * tal cual y no inventa `activated_by`.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params;

  let body: ActivateRunRequest = {};
  try {
    const text = await request.text();
    if (text.trim()) {
      body = JSON.parse(text) as ActivateRunRequest;
    }
  } catch {
    return Response.json(
      { error: "El cuerpo no es JSON válido.", status: 400 },
      { status: 400 },
    );
  }

  try {
    return Response.json(await activateRun(runId, body));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

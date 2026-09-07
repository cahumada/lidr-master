import type { NextRequest } from "next/server";

import { listAnswerSessions } from "@/lib/ai-service/answer";
import { toErrorPayload } from "@/lib/ai-service/base-client";

/**
 * `GET /api/answer/sessions` — relay to `GET /answer/sessions`.
 *
 * `limit` and `offset` travel if the browser sent them. Defaults and caps
 * live on the service; re-declaring them here would be a second ceiling.
 * || `limit` y `offset` viajan si el browser los mandó. Defaults y techos
 * viven en el servicio; re-declararlos acá sería un segundo techo.
 */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const limitRaw = params.get("limit");
  const offsetRaw = params.get("offset");

  try {
    return Response.json(
      await listAnswerSessions({
        limit: limitRaw === null || limitRaw === "" ? undefined : Number(limitRaw),
        offset: offsetRaw === null || offsetRaw === "" ? undefined : Number(offsetRaw),
      }),
    );
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

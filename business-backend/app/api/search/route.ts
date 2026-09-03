import type { NextRequest } from "next/server";

import { toErrorPayload } from "@/lib/ai-service/base-client";
import { search } from "@/lib/ai-service/search";

/**
 * `GET /api/search` -- the browser's only door to `GET /search`.
 * || `GET /api/search` -- la única puerta del browser hacia `GET /search`.
 *
 * The query params are relayed as they arrive; the service owns their defaults
 * and their validation, and re-declaring either here would create a second
 * source of truth that drifts.
 *
 * || Los query params se pasan como llegan; el servicio es dueño de sus
 * defaults y de su validación, y volver a declararlos acá crearía una segunda
 * fuente de verdad que se desincroniza.
 */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const q = params.get("q");
  if (!q) {
    return Response.json(
      { error: "Falta la consulta `q`.", status: 400 },
      { status: 400 },
    );
  }

  const asNumber = (name: string) => {
    const raw = params.get(name);
    if (raw === null || raw === "") return undefined;
    const value = Number(raw);
    return Number.isFinite(value) ? value : undefined;
  };
  const asBoolean = (name: string) => {
    const raw = params.get(name);
    return raw === null || raw === "" ? undefined : raw === "true";
  };

  try {
    const response = await search({
      q,
      limit: asNumber("limit"),
      max_per_document: asNumber("max_per_document"),
      module_code: params.get("module_code") ?? undefined,
      window_type_name: params.get("window_type_name") ?? undefined,
      lexical: asBoolean("lexical"),
      split: asBoolean("split"),
      rerank: asBoolean("rerank"),
    });
    return Response.json(response);
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

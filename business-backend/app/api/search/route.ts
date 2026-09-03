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

  // `.getAll`, not `.get`: several `module_code`/`window_type_name` params
  // are how the browser asks for an OR between values, and `.get` would
  // silently keep only the first one.
  // || `.getAll`, no `.get`: varios parámetros `module_code`/`window_type_name`
  // son cómo el browser pide un OR entre valores, y `.get` se quedaría con el
  // primero en silencio.
  const asList = (name: string) => {
    const values = params.getAll(name);
    return values.length > 0 ? values : undefined;
  };

  try {
    const response = await search({
      q,
      limit: asNumber("limit"),
      max_per_document: asNumber("max_per_document"),
      module_code: asList("module_code"),
      window_type_name: asList("window_type_name"),
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

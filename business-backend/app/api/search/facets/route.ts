import { toErrorPayload } from "@/lib/ai-service/base-client";
import { facets } from "@/lib/ai-service/search";

/**
 * `GET /api/search/facets` -- los valores que pueden elegir los filtros de
 * módulo y tipo de ventana, leídos del corpus y no escritos a mano en la
 * pantalla.
 *
 * || `GET /api/search/facets` -- the values the module and window-type
 * filters can pick from, read from the corpus rather than hard-coded in the
 * screen.
 */
export async function GET() {
  try {
    const response = await facets();
    return Response.json(response);
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

import { toErrorPayload } from "@/lib/ai-service/base-client";
import { refreshProviderModels } from "@/lib/ai-service/config";

/**
 * `POST /api/config/providers/[providerId]/models/refresh` — ask the provider
 * which models it serves and store the new ones, hidden.
 *
 * Hidden on arrival because a provider's listing is not a curated menu:
 * OpenAI's includes embeddings, audio and legacy completion models. Measured
 * on this project: 124 ids reported, 7 worth offering.
 *
 * || Le pregunta al proveedor qué modelos sirve y guarda los nuevos, ocultos.
 * Ocultos porque el listado de un proveedor no es un menú curado: el de OpenAI
 * incluye embeddings, audio y modelos de completion viejos. Medido acá: 124
 * ids reportados, 7 que vale la pena ofrecer.
 */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ providerId: string }> },
) {
  const { providerId } = await params;

  try {
    return Response.json(await refreshProviderModels(providerId));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

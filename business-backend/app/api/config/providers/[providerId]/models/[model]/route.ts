import { toErrorPayload } from "@/lib/ai-service/base-client";
import { deleteProviderModel, updateProviderModel } from "@/lib/ai-service/config";
import type { ModelUpdate } from "@/lib/ai-service/types";

/**
 * `PUT /api/config/providers/[providerId]/models/[model]` — visibility and
 * sampling capability. `DELETE` — remove it from the offering.
 *
 * The static `refresh` segment sits alongside this dynamic one; Next resolves
 * static segments first, so `models/refresh` is never captured as a model
 * named "refresh".
 * || El segmento estático `refresh` convive con este dinámico; Next resuelve
 * los estáticos primero, así `models/refresh` nunca se toma como un modelo
 * llamado "refresh".
 */
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ providerId: string; model: string }> },
) {
  const { providerId, model } = await params;

  let body: ModelUpdate;
  try {
    body = (await request.json()) as ModelUpdate;
  } catch {
    return Response.json(
      { error: "Cuerpo JSON inválido.", status: 400 },
      { status: 400 },
    );
  }

  try {
    return Response.json(await updateProviderModel(providerId, model, body));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ providerId: string; model: string }> },
) {
  const { providerId, model } = await params;

  try {
    await deleteProviderModel(providerId, model);
    return new Response(null, { status: 204 });
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

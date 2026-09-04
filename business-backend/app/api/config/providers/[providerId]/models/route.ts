import { toErrorPayload } from "@/lib/ai-service/base-client";
import { addProviderModel } from "@/lib/ai-service/config";
import type { ModelCreate } from "@/lib/ai-service/types";

/**
 * `POST /api/config/providers/[providerId]/models` — offer one more model.
 * || Ofrece un modelo más.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ providerId: string }> },
) {
  const { providerId } = await params;

  let body: ModelCreate;
  try {
    body = (await request.json()) as ModelCreate;
  } catch {
    return Response.json(
      { error: "Cuerpo JSON inválido.", status: 400 },
      { status: 400 },
    );
  }

  if (!body.model?.trim()) {
    return Response.json(
      { error: "Falta el nombre del modelo.", status: 422 },
      { status: 422 },
    );
  }

  try {
    return Response.json(await addProviderModel(providerId, body));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

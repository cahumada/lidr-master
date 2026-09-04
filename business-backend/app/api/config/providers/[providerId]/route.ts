import { toErrorPayload } from "@/lib/ai-service/base-client";
import { updateProvider } from "@/lib/ai-service/config";
import type { ProviderUpdate } from "@/lib/ai-service/types";

/**
 * `PUT /api/config/providers/[providerId]` — label, base URL, note, enabled.
 * NOT the credential: that has its own route, so a form editing a label never
 * carries a secret.
 * || NO la credencial: esa tiene su propia ruta, así un formulario que edita
 * un label nunca lleva un secreto.
 */
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ providerId: string }> },
) {
  const { providerId } = await params;

  let body: ProviderUpdate;
  try {
    body = (await request.json()) as ProviderUpdate;
  } catch {
    return Response.json(
      { error: "Cuerpo JSON inválido.", status: 400 },
      { status: 400 },
    );
  }

  try {
    return Response.json(await updateProvider(providerId, body));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

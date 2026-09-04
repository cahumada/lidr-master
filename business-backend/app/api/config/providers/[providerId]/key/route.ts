import { toErrorPayload } from "@/lib/ai-service/base-client";
import { clearProviderKey, setProviderKey } from "@/lib/ai-service/config";

/**
 * `PUT /api/config/providers/[providerId]/key` — store a credential.
 * `DELETE` — forget a stored one.
 *
 * Write-only by construction: neither verb returns a key, and the relay does
 * not log the body. The service stores it encrypted with a master key that
 * lives in ITS environment; what comes back is a `key_source` and a
 * four-character hint.
 *
 * There is deliberately no GET: an endpoint that reads a credential back is
 * the thing this design exists to not have.
 *
 * || Write-only por construcción: ningún verbo devuelve una clave, y el relay
 * no loguea el body. A propósito no hay GET: un endpoint que devuelve una
 * credencial es justo lo que este diseño existe para no tener.
 */
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ providerId: string }> },
) {
  const { providerId } = await params;

  let body: { api_key?: string };
  try {
    body = (await request.json()) as { api_key?: string };
  } catch {
    return Response.json(
      { error: "Cuerpo JSON inválido.", status: 400 },
      { status: 400 },
    );
  }

  const apiKey = body.api_key?.trim();
  if (!apiKey) {
    return Response.json(
      { error: "Falta la clave.", status: 422 },
      { status: 422 },
    );
  }

  try {
    return Response.json(await setProviderKey(providerId, apiKey));
  } catch (error) {
    // `toErrorPayload` carries the service's own message, which never
    // contains the value that was sent.
    // || El mensaje del servicio nunca contiene el valor que se mandó.
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ providerId: string }> },
) {
  const { providerId } = await params;

  try {
    return Response.json(await clearProviderKey(providerId));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

import { toErrorPayload } from "@/lib/ai-service/base-client";
import { startRebuild } from "@/lib/ai-service/corpus";
import type { RebuildRequest } from "@/lib/ai-service/types";

/**
 * `POST /api/corpus/rebuild` -- relays the request, including its refusals.
 * || `POST /api/corpus/rebuild` -- pasa el pedido, incluidas sus negativas.
 *
 * The `reset` guard lives in the service (`confirm_tenant_id` and
 * `confirm_doc_version` have to match the configured corpus) and this handler
 * does NOT re-implement it: it relays the 400 or the 409 with its message. The
 * screen enforces the same rule earlier, so a mismatch should never get here --
 * but if it does, the service's answer is the one that counts.
 *
 * || El guard de `reset` vive en el servicio (`confirm_tenant_id` y
 * `confirm_doc_version` tienen que coincidir con el corpus configurado) y este
 * handler NO lo reimplementa: pasa el 400 o el 409 con su mensaje. La pantalla
 * aplica la misma regla antes, así que un desajuste no debería llegar acá --
 * pero si llega, la respuesta del servicio es la que vale.
 */
export async function POST(request: Request) {
  let body: RebuildRequest;
  try {
    body = (await request.json()) as RebuildRequest;
  } catch {
    return Response.json(
      { error: "El cuerpo no es JSON válido.", status: 400 },
      { status: 400 },
    );
  }

  try {
    return Response.json(await startRebuild(body), { status: 202 });
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

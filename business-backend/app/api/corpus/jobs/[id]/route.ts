import { toErrorPayload } from "@/lib/ai-service/base-client";
import { job } from "@/lib/ai-service/corpus";

/**
 * `GET /api/corpus/jobs/{id}` -- one job's state, for the polling screen.
 * || El estado de un job, para la pantalla que sondea.
 *
 * `params` is a Promise in Next 16 (synchronous access was removed in this
 * major), so it is awaited.
 * || `params` es una Promise en Next 16 (el acceso síncrono se eliminó en esta
 * major), así que se espera.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  try {
    return Response.json(await job(id));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

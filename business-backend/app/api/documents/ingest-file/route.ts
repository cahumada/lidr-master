import { toErrorPayload } from "@/lib/ai-service/base-client";
import { ingestFile } from "@/lib/ai-service/documents";

/**
 * `POST /api/documents/ingest-file` -- relays the upload to the AI service.
 * || `POST /api/documents/ingest-file` -- pasa la subida al servicio IA.
 *
 * The file travels through; nothing is written to disk here and nothing is
 * persisted there -- the endpoint upstream returns the chunks and forgets them.
 *
 * || El archivo pasa de largo; acá no se escribe nada en disco y allá no se
 * persiste nada -- el endpoint de arriba devuelve los chunks y los olvida.
 */
export async function POST(request: Request) {
  let file: FormDataEntryValue | null;
  try {
    const form = await request.formData();
    file = form.get("file");
  } catch {
    return Response.json(
      { error: "El cuerpo no es un formulario multipart válido.", status: 400 },
      { status: 400 },
    );
  }

  if (!(file instanceof File)) {
    return Response.json(
      {
        error: "Falta el archivo en el campo `file`.",
        status: 400,
      },
      { status: 400 },
    );
  }

  try {
    return Response.json(await ingestFile(file));
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}

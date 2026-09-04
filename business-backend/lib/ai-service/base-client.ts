import "server-only";

/**
 * The ONLY layer that speaks HTTP to the AI service.
 * || La ÚNICA capa que habla HTTP con el servicio IA.
 *
 * `server-only` is the enforcement, not a convention: importing this from a
 * Client Component is a build error, so `AI_SERVICE_URL` cannot reach the
 * browser by accident.
 *
 * || `server-only` es la garantía, no una convención: importar esto desde un
 * Client Component es un error de build, así que `AI_SERVICE_URL` no puede
 * llegar al browser por descuido.
 */

/** Default timeout. The rebuild endpoint answers in ms (it returns a job id); search with rerank takes seconds. || Timeout por defecto. */
const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * An error the AI service itself produced, with its status kept.
 * || Un error que produjo el propio servicio IA, con su status conservado.
 *
 * The status is load-bearing upstream: 409 on `/corpus/rebuild` means "a job is
 * already running" and is shown as state, not as a failure.
 *
 * || El status importa arriba: un 409 en `/corpus/rebuild` significa "ya hay un
 * job corriendo" y se muestra como estado, no como falla.
 */
export class AiServiceError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "AiServiceError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * The service is unreachable -- a different problem from the service saying no.
 * || El servicio no responde -- otro problema distinto de que el servicio diga que no.
 *
 * Note the message is Spanish only, not bilingual: the repo's `EN || ES` rule
 * covers comments, docstrings and Swagger descriptions -- text written for
 * whoever reads the code. This string is rendered to a user, and a user should
 * not be shown the same sentence twice.
 *
 * || El mensaje va solo en español, no bilingüe: la regla `EN || ES` del repo
 * cubre comentarios, docstrings y descripciones de Swagger -- texto para quien
 * lee el código. Esta cadena se le muestra a una persona, y a una persona no se
 * le muestra la misma frase dos veces.
 */
export class AiServiceUnreachable extends Error {
  constructor(cause: unknown) {
    super("No se pudo contactar al servicio IA.");
    this.name = "AiServiceUnreachable";
    this.cause = cause;
  }
}

function baseUrl(): string {
  const url = process.env.AI_SERVICE_URL;
  if (!url) {
    throw new Error("AI_SERVICE_URL no está configurada.");
  }
  return url.replace(/\/$/, "");
}

/**
 * FastAPI puts its message in `detail`, which is a string for an `HTTPException`
 * and a list of objects for a validation error. Both are flattened to a line a
 * human can read.
 *
 * || FastAPI pone su mensaje en `detail`: un string para `HTTPException` y una
 * lista de objetos para un error de validación. Los dos se aplanan a una línea
 * que una persona puede leer.
 */
async function detailOf(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) return `${response.status} ${response.statusText}`;
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    const detail = body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          const entry = item as { loc?: unknown[]; msg?: string };
          const where = Array.isArray(entry.loc) ? entry.loc.join(".") : "";
          return where ? `${where}: ${entry.msg ?? ""}` : (entry.msg ?? "");
        })
        .join(" · ");
    }
    return text;
  } catch {
    return text;
  }
}

async function call(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...rest } = init;
  const signal = AbortSignal.timeout(timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${baseUrl()}${path}`, {
      ...rest,
      signal,
      // Never cached: every one of these is either a live query or a mutation.
      // || Nunca cacheado: cada uno de estos es una consulta viva o una mutación.
      cache: "no-store",
    });
  } catch (error) {
    throw new AiServiceUnreachable(error);
  }

  if (!response.ok) {
    throw new AiServiceError(response.status, await detailOf(response));
  }
  return response;
}

export async function getJson<T>(
  path: string,
  params?: Record<string, string | number | boolean | string[] | undefined>,
  timeoutMs?: number,
): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === "") continue;
    // An array becomes a repeated param (`?module_code=CA&module_code=DF`),
    // which is what FastAPI's `list[str] | None` Query param expects.
    // || Un arreglo se vuelve un parámetro repetido, que es lo que espera un
    // Query param `list[str] | None` de FastAPI.
    if (Array.isArray(value)) {
      for (const item of value) query.append(key, item);
    } else {
      query.set(key, String(value));
    }
  }
  const suffix = query.size > 0 ? `?${query}` : "";
  const response = await call(`${path}${suffix}`, { timeoutMs });
  return (await response.json()) as T;
}

export async function postJson<T>(
  path: string,
  body: unknown,
  timeoutMs?: number,
): Promise<T> {
  const response = await call(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    timeoutMs,
  });
  return (await response.json()) as T;
}

export async function putJson<T>(
  path: string,
  body: unknown,
  timeoutMs?: number,
): Promise<T> {
  const response = await call(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    timeoutMs,
  });
  return (await response.json()) as T;
}

export async function deleteJson<T>(
  path: string,
  timeoutMs?: number,
): Promise<T> {
  const response = await call(path, { method: "DELETE", timeoutMs });
  return (await response.json()) as T;
}

/**
 * DELETE that returns 204 with no body. Separate from `deleteJson` because
 * calling `.json()` on an empty body throws, and "the delete worked" should
 * not surface as a parse error.
 * || DELETE que devuelve 204 sin body. Separada de `deleteJson` porque llamar
 * `.json()` sobre un body vacío lanza, y "el borrado funcionó" no debería
 * aparecer como un error de parseo.
 */
export async function deleteNoContent(
  path: string,
  timeoutMs?: number,
): Promise<void> {
  await call(path, { method: "DELETE", timeoutMs });
}

export async function postFormData<T>(
  path: string,
  form: FormData,
  timeoutMs?: number,
): Promise<T> {
  // No Content-Type header on purpose: fetch sets it with the multipart
  // boundary, and setting it by hand produces a body the server cannot parse.
  // || Sin header Content-Type a propósito: fetch lo pone con el boundary del
  // multipart, y ponerlo a mano produce un body que el servidor no puede parsear.
  const response = await call(path, {
    method: "POST",
    body: form,
    timeoutMs,
  });
  return (await response.json()) as T;
}

/**
 * POST JSON and accept several success status codes — e.g. 200 and 202 on
 * `/answer/agentic`, where 202 is a deliberate pause, not a failure.
 * || POST JSON aceptando varios códigos de éxito — p. ej. 200 y 202 en
 * `/answer/agentic`, donde 202 es una pausa deliberada, no un fallo.
 */
export async function postJsonAllowingStatuses<T>(
  path: string,
  body: unknown,
  allowedStatuses: number[],
  timeoutMs?: number,
): Promise<{ status: number; data: T }> {
  const response = await callAllowingStatuses(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    timeoutMs,
    allowedStatuses,
  });
  return { status: response.status, data: (await response.json()) as T };
}

async function callAllowingStatuses(
  path: string,
  init: RequestInit & { timeoutMs?: number; allowedStatuses: number[] },
): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, allowedStatuses, ...rest } = init;
  const signal = AbortSignal.timeout(timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${baseUrl()}${path}`, {
      ...rest,
      signal,
      cache: "no-store",
    });
  } catch (error) {
    throw new AiServiceUnreachable(error);
  }

  if (!allowedStatuses.includes(response.status)) {
    throw new AiServiceError(response.status, await detailOf(response));
  }
  return response;
}

/** Shape the route handlers relay to the browser. || Forma que los route handlers pasan al browser. */
export interface ErrorPayload {
  error: string;
  status: number;
}

/**
 * Turn any thrown error into a status + message the browser can render.
 * Nothing internal leaks: an unexpected error becomes a generic 500 line.
 *
 * || Convierte cualquier error en un status + mensaje que el browser puede
 * mostrar. No se filtra nada interno: un error inesperado es un 500 genérico.
 */
export function toErrorPayload(error: unknown): ErrorPayload {
  if (error instanceof AiServiceError) {
    return { error: error.detail, status: error.status };
  }
  if (error instanceof AiServiceUnreachable) {
    return { error: error.message, status: 502 };
  }
  if (error instanceof Error && error.message.includes("AI_SERVICE_URL")) {
    return { error: error.message, status: 500 };
  }
  return { error: "Error inesperado en la consola web.", status: 500 };
}

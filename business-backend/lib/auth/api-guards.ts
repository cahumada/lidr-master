import { auth } from "@/auth"
import { mayCallAdminRoute } from "@/lib/auth/roles"

/**
 * Role gate for route handlers, which the `(admin)/` layout does not reach.
 *
 * Screens are gated by where their file sits: a page under `app/(console)/(admin)/`
 * is protected by that group's layout. That is a good decision for screens and
 * it protects no route handler, because `app/api/` is not under `(admin)/`.
 *
 * It matters here because `/answer` is NOT an admin screen — anyone with a
 * session opens it. So hiding the link is presentation, and the refusal has to
 * happen on the server, before the AI service is called at all.
 *
 * || Gate de rol para route handlers, al que el layout de `(admin)/` no llega.
 * Las pantallas están protegidas por dónde vive su archivo; `app/api/` no vive
 * ahí. Importa acá porque `/answer` NO es una pantalla de administración:
 * ocultar el link es presentación, y el rechazo va en el servidor.
 */

/**
 * ``null`` when the caller may proceed, or the 403 to return as-is.
 *
 * Returning the response instead of throwing keeps the refusal visible at the
 * call site: a handler that forgets to use the result does not silently pass.
 *
 * || ``null`` si puede seguir, o el 403 para devolver tal cual. Devolver la
 * respuesta —en vez de lanzar— deja el rechazo visible en el call site.
 */
export async function requireAdmin(): Promise<Response | null> {
  const session = await auth()
  if (!session?.user || !mayCallAdminRoute(session.user.role)) {
    return Response.json(
      {
        error: "Solo un administrador puede ver esto.",
        status: 403,
      },
      { status: 403 },
    )
  }
  return null
}

import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

/**
 * `proxy.ts` — the cheap gate: is there a session at all?
 *
 * `proxy` and NOT `middleware`: the `middleware` file convention is
 * deprecated in Next 16 and renamed to `proxy`. Same behaviour, different
 * file and export name.
 *
 * It answers ONE question and does not look at roles. Next's own docs say
 * why: "Proxy is meant to be invoked separately of your render code and in
 * optimized cases deployed to your CDN […] you should not attempt relying on
 * shared modules or globals". It runs at the edge, far from the data, and a
 * check that is skipped there has no second line. So: optimistic at the
 * edge, true near the data — the role is verified in `app/(console)/layout.tsx`.
 *
 * The cookie is read, not verified. That is deliberate and it is why this is
 * a gate and not authorization: a forged cookie gets past here and dies at
 * the layout, which resolves the real session.
 *
 * || `proxy` y NO `middleware`: el convention `middleware` está deprecado en
 * Next 16 y renombrado. Responde UNA pregunta y no mira roles: corre en el
 * borde, lejos de los datos, y una comprobación que se saltea ahí no tiene
 * segunda línea. La cookie se lee, no se verifica — por eso esto es un gate y
 * no autorización: una cookie falsificada pasa acá y muere en el layout.
 */

const SESSION_COOKIES = [
  "authjs.session-token",
  "__Secure-authjs.session-token",
]

export function proxy(request: NextRequest) {
  const hasSession = SESSION_COOKIES.some(
    (name) => request.cookies.get(name)?.value,
  )
  if (hasSession) return NextResponse.next()

  // Where they were going, so the login can send them back instead of
  // dumping everyone on the home page.
  // || A dónde iban, para que el login los devuelva ahí en vez de dejar a
  // todos en la portada.
  const login = new URL("/login", request.url)
  const target = request.nextUrl.pathname + request.nextUrl.search
  if (target && target !== "/") login.searchParams.set("next", target)
  return NextResponse.redirect(login)
}

export const config = {
  // Everything except the auth endpoints, the two screens you reach without
  // an account, Next's own assets, and static brand files. `/api/auth/*`
  // must stay open or signing in would require being signed in — and
  // `/register` for the same reason, one step earlier. `/brand/*` is the
  // favicon: the optimizer fetching it without a cookie used to get the
  // login HTML and report "isn't a valid image".
  // || Todo menos auth, login/register, assets de Next y la marca estática.
  // `/brand/*` es el favicon: el optimizer, sin cookie, recibía el HTML del
  // login y decía que no era una imagen.
  matcher: [
    "/((?!api/auth|login|register|_next/static|_next/image|favicon.ico|brand/|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
}

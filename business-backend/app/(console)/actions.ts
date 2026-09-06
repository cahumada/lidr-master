"use server"

import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { auth, signIn, signOut } from "@/auth"

/**
 * Sign out, as a Server Action.
 *
 * A POST and not a link, because a GET that logs you out is a GET that any
 * page can fire at you with an `<img>` tag. A form action goes through the
 * framework's action endpoint, which carries its own origin check.
 *
 * Auth.js `signOut` only expires the session cookie. The rest of the jar —
 * CSRF, callback URL, leftover PKCE/state from a Google round trip — stays
 * until the browser drops it. After a failed OAuth attempt those leftovers
 * are exactly what you still see in DevTools. So we expire every cookie we
 * can see, then send them to `/login` ourselves.
 *
 * `redirect: false` and not `redirectTo`: if `signOut` redirected, the
 * sweep below would never run.
 *
 * || Auth.js `signOut` solo vence la cookie de sesión. El resto —CSRF,
 * callback, PKCE/state de una ida a Google— queda. Por eso vencemos todas
 * las cookies que vemos y mandamos a `/login` nosotros.
 */
export async function signOutAction(): Promise<void> {
  await signOut({ redirect: false })
  await clearStoredCookies()
  redirect("/login")
}

/**
 * Auth.js cookie names, both the localhost set and the `__Secure-` /
 * `__Host-` set used on HTTPS. Chunked session tokens (`*.0`, `*.1`) are
 * picked up by `getAll()`, not listed here.
 *
 * || Nombres de cookie de Auth.js, el set de localhost y el de HTTPS. Los
 * tokens partidos los junta `getAll()`.
 */
const AUTHJS_COOKIE_NAMES = [
  "authjs.session-token",
  "__Secure-authjs.session-token",
  "authjs.callback-url",
  "__Secure-authjs.callback-url",
  "authjs.csrf-token",
  "__Host-authjs.csrf-token",
  "authjs.pkce.code_verifier",
  "__Secure-authjs.pkce.code_verifier",
  "authjs.state",
  "__Secure-authjs.state",
  "authjs.nonce",
  "__Secure-authjs.nonce",
  "authjs.challenge",
  "__Secure-authjs.challenge",
] as const

async function clearStoredCookies(): Promise<void> {
  const jar = await cookies()
  const names = new Set<string>([
    ...AUTHJS_COOKIE_NAMES,
    ...jar.getAll().map((cookie) => cookie.name),
  ])
  for (const name of names) {
    // Same `path` Auth.js used when it set them. A delete that omits it
    // misses the cookie the browser still holds.
    // || El mismo `path` con el que Auth.js las escribió.
    jar.delete({ name, path: "/" })
  }
}

/**
 * Links Google to the signed-in account.
 *
 * Auth.js will only attach an OAuth identity to a user that is *already*
 * authenticated — that is the safe linking the login screen cannot do.
 *
 * || Vincula Google a la cuenta que ya tiene sesión. Auth.js solo adjunta
 * una identidad OAuth a alguien que YA está autenticado.
 */
export async function linkOwnGoogle(): Promise<void> {
  const session = await auth()
  if (!session?.user?.id) return

  await signIn("google", { redirectTo: "/" })
}

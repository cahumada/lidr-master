"use server"

import { AuthError } from "next-auth"

import { signIn } from "@/auth"
import { safeRedirect } from "@/lib/auth/safe-redirect"

/**
 * The two ways in, as Server Actions.
 *
 * Server Actions and not `next-auth/react`: the credentials path would
 * otherwise mean shipping the password from a browser handler, and the whole
 * point of `authorize()` running on the server is that the password is read
 * in one place. This way the form posts, the action runs where the hash is,
 * and no auth client reaches the bundle.
 *
 * || Las dos formas de entrar, como Server Actions. Server Actions y no
 * `next-auth/react`: con el cliente, la contraseña saldría desde un handler
 * del browser, y la gracia de que `authorize()` corra en el servidor es que
 * la contraseña se lee en un solo lugar.
 */

export type LoginState = { error?: string }

/**
 * One message for every failure, matching `authorize()` in `auth.ts`, which
 * returns the same `null` for an unknown email, an account with no password
 * and a wrong password. Splitting them here would undo that: a form that says
 * "that email does not exist" is an account enumerator with a nicer face.
 *
 * || Un solo mensaje para toda falla, igual que `authorize()`. Separarlos acá
 * desharía aquello: un formulario que dice «ese email no existe» es un
 * enumerador de cuentas con mejor cara.
 */
const GENERIC_FAILURE = "Email o contraseña incorrectos."

export async function signInWithPassword(
  _prev: LoginState,
  formData: FormData,
): Promise<LoginState> {
  const email = String(formData.get("email") ?? "")
  const password = String(formData.get("password") ?? "")
  const next = safeRedirect(String(formData.get("next") ?? ""))

  if (!email || !password) {
    return { error: "Completá email y contraseña." }
  }

  try {
    await signIn("credentials", { email, password, redirectTo: next })
  } catch (error) {
    // `signIn` succeeds by THROWING: a successful sign-in ends in
    // `redirect()`, which works by throwing a `NEXT_REDIRECT` that the
    // framework catches upstream. Swallowing every error here would swallow
    // the success too and leave the user on the form, signed in, with no way
    // to tell. So: handle `AuthError`, re-throw everything else.
    // || `signIn` tiene éxito LANZANDO: un login exitoso termina en
    // `redirect()`, que funciona lanzando un `NEXT_REDIRECT` que el framework
    // atrapa más arriba. Tragarse todo error acá se tragaría también el
    // éxito, y dejaría al usuario en el formulario, ya logueado, sin
    // enterarse.
    if (error instanceof AuthError) return { error: GENERIC_FAILURE }
    throw error
  }

  // Unreachable in practice — see above. Here so the function has a return
  // type that does not lie.
  // || Inalcanzable en la práctica. Está para que el tipo de retorno no mienta.
  return {}
}

export async function signInWithGoogle(formData: FormData): Promise<void> {
  const next = safeRedirect(String(formData.get("next") ?? ""))
  // No try/catch: a rejection by the `signIn` callback in `auth.ts` — an
  // email that is not a user — happens after the round trip to Google, on
  // `/api/auth/callback/google`, not here. Auth.js sends that one back to
  // `pages.error`, which is this same screen, with `?error=AccessDenied`.
  // || Sin try/catch: el rechazo del callback `signIn` de `auth.ts` ocurre
  // después de la vuelta por Google, no acá. Auth.js lo manda a
  // `pages.error`, que es esta misma pantalla, con `?error=AccessDenied`.
  await signIn("google", { redirectTo: next })
}

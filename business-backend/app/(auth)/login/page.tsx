import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { auth } from "@/auth"
import { safeRedirect } from "@/lib/auth/safe-redirect"

import { LoginForm } from "./login-form"

export const metadata: Metadata = {
  title: "Entrar · Visual Time RAG",
}

/**
 * The one screen `proxy.ts` lets through without a session.
 *
 * It is also `pages.error` in `auth.ts`, so a rejected Google sign-in lands
 * back here with `?error=…` instead of on Auth.js's own error page. Same
 * screen, message on top, form still there to try the other method.
 *
 * || La única pantalla que `proxy.ts` deja pasar sin sesión. Es además
 * `pages.error` en `auth.ts`, así que un login de Google rechazado vuelve acá
 * con `?error=…` en vez de caer en la página de error de Auth.js.
 */

/**
 * Auth.js error codes, translated.
 *
 * `AccountDisabled` is the one this console produces on purpose: the `signIn`
 * callback returns `/login?error=AccountDisabled` rather than `false`,
 * precisely so this message can exist. It only ever reaches someone who
 * already proved that account's password, so it tells a stranger nothing.
 *
 * `OAuthAccountNotLinked` comes from Auth.js and is the visible face of
 * `allowDangerousEmailAccountLinking: false`. Left untranslated it reads as a
 * bug; it is the console refusing to join two accounts by email address.
 *
 * Anything else gets a message that admits it does not know. Guessing at a
 * cause the user cannot verify is worse than saying "try again".
 *
 * || `AccountDisabled` es el que esta consola produce a propósito: el callback
 * `signIn` devuelve una URL en vez de `false` justamente para que este mensaje
 * pueda existir, y le llega a alguien que ya probó su contraseña.
 * `OAuthAccountNotLinked` viene de Auth.js y es la cara visible de no vincular
 * cuentas por email; sin traducir parece un bug.
 */
const ERROR_MESSAGES: Record<string, string> = {
  AccountDisabled:
    "Tu cuenta todavía no está habilitada. Un administrador tiene que hacerlo antes de que puedas entrar.",
  OAuthAccountNotLinked:
    "Ese email ya tiene contraseña. El botón de Google no sirve todavía. Entrá abajo con email y contraseña; adentro, tocá Vincular Google en el header. Después sí vas a poder entrar con Google.",
  AccessDenied: "No se pudo entrar con esa cuenta.",
  Verification: "El enlace venció o ya se usó. Probá entrar de nuevo.",
  // Auth.js collapses EVERY failure before the redirect to the provider into
  // this one code — a missing credential, yes, but also the server simply not
  // being able to reach Google. The first version of this message asserted
  // "configuration is missing", and cost an hour of looking at environment
  // variables while the real cause was a TLS handshake that antivirus
  // interception broke. A message may not name a cause it does not know.
  // || Auth.js mete TODA falla previa al redirect al proveedor en este único
  // código: falta una credencial, sí, pero también que el servidor no pueda
  // alcanzar a Google. La primera versión de este mensaje afirmaba «falta
  // configuración» y costó una hora mirando variables de entorno mientras la
  // causa real era un handshake TLS roto por la intercepción del antivirus.
  // Un mensaje no puede nombrar una causa que no conoce.
  Configuration:
    "El servidor no pudo iniciar el login con Google: falta una credencial o no llega a Google. La causa exacta está en el log del servidor.",
}

const UNKNOWN_ERROR = "No se pudo entrar. Probá de nuevo."

export default async function LoginPage(props: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const searchParams = await props.searchParams
  const next = safeRedirect(searchParams.next)

  // Already signed in: send them in rather than showing a form that would
  // sign them in as who they already are.
  // || Ya tiene sesión: adentro, en vez de mostrarle un formulario para
  // entrar como quien ya es.
  const session = await auth()
  if (session?.user) redirect(next)

  const code =
    typeof searchParams.error === "string" ? searchParams.error : undefined
  const initialError = code
    ? (ERROR_MESSAGES[code] ?? UNKNOWN_ERROR)
    : undefined

  return (
    <LoginForm
      next={next}
      initialError={initialError}
      hideGoogle={code === "OAuthAccountNotLinked"}
    />
  )
}

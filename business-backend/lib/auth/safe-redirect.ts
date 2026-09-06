/**
 * Narrow a `?next=` parameter to somewhere inside this console.
 *
 * `proxy.ts` puts the requested path in the query so the login can send
 * people back where they were going, and a query parameter is written by
 * whoever composed the URL — which is to say, by anyone. Handing it to
 * `redirect()` unchecked is the open-redirect bug: a link to our own
 * `/login?next=https://evil.example` would show our sign-in form and then
 * hand the browser to somebody else, with our domain in the referrer.
 *
 * So: an allow-list of shapes, not a blocklist of bad ones.
 *
 * `//host` is the case worth naming, because it does not look like a URL and
 * is one: a browser reads a protocol-relative URL as "same scheme, that
 * host". `\\host` likewise, since browsers normalise the backslashes.
 *
 * || Angosta un `?next=` a algún lugar de esta consola. El parámetro lo
 * escribe quien armó la URL —o sea, cualquiera—, y pasárselo a `redirect()`
 * sin mirar es el bug de open redirect. Lista blanca de formas, no lista
 * negra de las malas. El caso que vale nombrar es `//host`: no parece una URL
 * y lo es — el browser lee una URL protocol-relative como «mismo esquema, ese
 * host». `\\host` igual, porque el browser normaliza las barras.
 */

export const DEFAULT_REDIRECT = "/"

export function safeRedirect(next: string | string[] | undefined): string {
  // Repeated `?next=` gives an array. There is no sensible "which one did
  // they mean", so take neither.
  // || Un `?next=` repetido da un array. No hay «cuál quiso» sensato.
  if (typeof next !== "string") return DEFAULT_REDIRECT
  if (!next.startsWith("/")) return DEFAULT_REDIRECT
  if (next.startsWith("//") || next.startsWith("/\\")) return DEFAULT_REDIRECT

  // Bouncing back to the login on success would loop.
  // || Volver al login después de entrar sería un bucle.
  if (next === "/login" || next.startsWith("/login?")) return DEFAULT_REDIRECT

  return next
}

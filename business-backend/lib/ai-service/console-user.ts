/**
 * The header that tells the AI service who is asking.
 *
 * Its own module, and deliberately NOT `server-only`: the rule it encodes is
 * small, load-bearing and worth testing, and `server-only` would make it
 * unimportable from a test. What must not leak is the token and the service
 * URL, and those stay in `base-client.ts`.
 *
 * || El header que le dice al servicio IA quién pregunta. Módulo propio y a
 * propósito SIN `server-only`: la regla que codifica es chica, sostiene algo
 * importante y conviene testearla, y `server-only` la volvería inimportable
 * desde un test. Lo que no puede escaparse es el token y la URL del servicio,
 * y eso se queda en `base-client.ts`.
 */

export const CONSOLE_USER_HEADER = "X-Console-User";

/** What the service accepts; longer than this is refused there, not truncated. */
const MAX_ID_CHARS = 64;

/**
 * The header for this user id, or nothing at all.
 *
 * Nothing is the right answer for no session: the service reads an absent
 * header as "the conversations that have no owner either", so the failure mode
 * is seeing nothing instead of seeing everybody's. An invented value would be
 * the opposite kind of mistake.
 *
 * An over-long id is dropped rather than cut: cutting would make two different
 * users collide into one owner, which is the failure this exists to prevent.
 *
 * || El header para este id de usuario, o nada. Nada es la respuesta correcta
 * sin sesión: el servicio lee la ausencia como «las que tampoco tienen dueño»,
 * así que la falla es no ver nada en vez de ver las de todos. Un id demasiado
 * largo se descarta y no se corta: cortarlo haría colisionar dos usuarios
 * distintos en un mismo dueño.
 */
export function consoleUserHeaderFor(
  userId: string | null | undefined,
): Record<string, string> {
  const trimmed = userId?.trim();
  if (!trimmed || trimmed.length > MAX_ID_CHARS) return {};
  return { [CONSOLE_USER_HEADER]: trimmed };
}

import bcrypt from "bcryptjs"

/**
 * Hashing and verification for the credentials provider.
 *
 * Deliberately free of imports from the rest of the app so it can be unit
 * tested without a database or a request — this is the logic
 * `bff-standards.md` §Tests had in mind when it said that a BFF growing past
 * relay is what justifies a runner.
 *
 * `bcryptjs` and not a native binding: the console deploys to Vercel's
 * serverless functions, and a package that compiles on install is a build
 * that can break on someone else's runtime. Speed is not the axis here — the
 * cost factor is, and it is explicit below.
 *
 * || Hasheo y verificación para el proveedor de credenciales. Sin imports del
 * resto de la app, para poder testearlo sin base y sin request. `bcryptjs` y
 * no un binding nativo: la consola despliega en funciones serverless de
 * Vercel, y un paquete que compila al instalar es un build que puede romperse
 * en el runtime de otro.
 */

/**
 * Cost factor. 12 is the current sane default: roughly 250 ms per hash on a
 * serverless CPU, which is slow enough to hurt an attacker and fast enough
 * not to time out a login. Raising it later is safe — the cost is encoded in
 * the hash, so old hashes keep verifying.
 * || Factor de costo. 12 es el default sensato de hoy. Subirlo después es
 * seguro: el costo va codificado en el hash, así que los viejos siguen
 * verificando.
 */
const COST = 12

export async function hashPassword(plain: string): Promise<string> {
  if (!plain) {
    throw new Error("La contraseña no puede estar vacía. || Password is empty.")
  }
  return bcrypt.hash(plain, COST)
}

/**
 * Whether ``plain`` matches ``hash``.
 *
 * Returns false instead of throwing when the account has no password — a
 * Google-only user has `passwordHash = null`, and asking "is this the right
 * password" about an account that has none is a legitimate question with a
 * boring answer.
 *
 * || Si ``plain`` coincide con ``hash``. Devuelve false en vez de lanzar
 * cuando la cuenta no tiene contraseña: un usuario que solo entra por Google
 * tiene `passwordHash = null`, y preguntar si una contraseña coincide con una
 * cuenta que no tiene es una pregunta legítima con una respuesta aburrida.
 */
export async function verifyPassword(
  plain: string,
  hash: string | null | undefined,
): Promise<boolean> {
  if (!plain || !hash) return false
  return bcrypt.compare(plain, hash)
}

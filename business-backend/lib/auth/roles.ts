/**
 * The two roles and what each one may reach.
 *
 * No import from Prisma, `next-auth` or the database: this is a pure lookup
 * so it can be unit tested on its own and imported from anywhere — including
 * `lib/console-nav.ts`, which is a Client-side module and must not pull a
 * database client into the browser bundle.
 *
 * The cut is NOT "reads vs writes". It is **what stays broken if it is used
 * wrong**: `/documents` writes but does not persist (it previews chunking),
 * while `/corpus` triggers a destructive rebuild, `/models` stores provider
 * credentials, `/agents` changes how the system answers *everyone*, and
 * `/users` decides who gets in at all.
 *
 * || Los dos roles y qué alcanza cada uno. Sin imports de Prisma, `next-auth`
 * ni la base: es una tabla pura, testeable sola e importable desde cualquier
 * lado — incluido `lib/console-nav.ts`, que es de cliente y no puede arrastrar
 * un cliente de base al bundle del browser. El corte NO es «lee vs escribe»
 * sino qué queda roto si se usa mal.
 */

export const ROLES = ["usuario", "administrador"] as const

export type Role = (typeof ROLES)[number]

/**
 * The role every new account starts with. Declared here AND defaulted in the
 * database, so a row inserted by hand cannot be born an administrator.
 * || El rol con el que nace toda cuenta. Declarado acá Y con default en la
 * base, para que una fila insertada a mano no nazca administradora.
 */
export const DEFAULT_ROLE: Role = "usuario"

/**
 * Screens that require `administrador`. Everything not listed is open to any
 * session. A deny-list and not an allow-list on purpose: a screen added
 * tomorrow is readable by default, which is the safe failure for a console
 * whose risk lives in the five routes below and not in reading the corpus.
 * || Pantallas que exigen `administrador`. Lo que no está listado queda
 * abierto a cualquier sesión. Deny-list a propósito: una pantalla nueva nace
 * legible, que es el fallo seguro acá — el riesgo vive en estas cinco rutas
 * y no en leer el corpus.
 */
const ADMIN_ONLY = ["/agents", "/models", "/corpus", "/users", "/usage"] as const

/**
 * Whether ``role`` may open ``pathname``.
 *
 * Prefix match so `/agents/flow` inherits from `/agents`: a sub-screen of a
 * restricted section cannot be looser than its parent by accident.
 *
 * || Si ``role`` puede abrir ``pathname``. Match por prefijo para que
 * `/agents/flow` herede de `/agents`: una subpantalla de una sección
 * restringida no puede quedar más floja que su padre por descuido.
 */
export function canAccess(role: Role | undefined, pathname: string): boolean {
  if (!isAdminOnly(pathname)) return true
  return role === "administrador"
}

export function isAdminOnly(pathname: string): boolean {
  return ADMIN_ONLY.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
}

/**
 * Narrow an unknown value — what comes out of a JWT — to a role, falling back
 * to the least privileged one. A token with a role this build does not know
 * must not be treated as an administrator.
 * || Angosta un valor desconocido —lo que sale de un JWT— a un rol, cayendo
 * al menos privilegiado. Un token con un rol que este build no conoce no
 * puede tratarse como administrador.
 */
export function asRole(value: unknown): Role {
  return ROLES.includes(value as Role) ? (value as Role) : DEFAULT_ROLE
}

/**
 * Whether ``role`` may call an administration ROUTE HANDLER.
 *
 * Lives here and not next to the handler guard for the reason this whole file
 * exists: it must be importable and unit-testable without pulling `next-auth`
 * or a database client along. `lib/auth/api-guards.ts` is the server-only
 * wrapper that resolves the session and calls this.
 *
 * Screens are gated by where their file sits, under `(admin)/`. Route handlers
 * are not: `app/api/` is outside that group, so they need this.
 *
 * || Si ``role`` puede llamar un ROUTE HANDLER de administración. Vive acá por
 * la razón por la que existe este archivo: tiene que ser importable y testeable
 * sin arrastrar `next-auth` ni un cliente de base.
 */
export function mayCallAdminRoute(role: unknown): boolean {
  // `asRole` floors an unknown value to the least privileged role, so a token
  // carrying a role this build does not know is never an administrator.
  // || `asRole` aterriza lo desconocido al rol menos privilegiado.
  return asRole(role) === "administrador"
}

import type { Role } from "@/lib/auth/roles"

/**
 * The rules that say when an administrator may NOT do something to an
 * account. Pure functions, no Prisma and no session: they take the facts and
 * return a reason or `null`.
 *
 * Separated so they can be unit tested without a database — and, more to the
 * point, so the same rule is used by the Server Action that enforces it and
 * by the screen that greys out the button. Two copies of "can I do this"
 * drift, and the copy that drifts is always the one nobody tested.
 *
 * They return the message rather than a boolean: a refusal the user cannot
 * explain to themselves is a bug report waiting to happen, and the reason is
 * the only part of this that is hard to reconstruct later.
 *
 * || Las reglas de cuándo un administrador NO puede hacer algo con una
 * cuenta. Funciones puras, sin Prisma y sin sesión. Separadas para poder
 * testearlas sin base y —sobre todo— para que la Server Action que prohíbe y
 * la pantalla que desactiva el botón usen la MISMA regla: dos copias de
 * «¿puedo?» se separan, y la que se separa es siempre la que nadie testeó.
 * Devuelven el mensaje y no un booleano: un rechazo que la persona no se
 * puede explicar es un reporte de bug esperando a pasar.
 */

export type Refusal = string | null

export type TargetAccount = {
  id: string
  role: Role
  disabledAt: Date | null
}

/**
 * Whether ``actorId`` may change ``target``'s role.
 *
 * Nobody changes their own — not against an attack (an administrator who
 * wants to hurt themselves already can) but against the accident: your own
 * row is the one closest to hand in the list. It also means promoting
 * yourself is impossible even if `/users` were ever opened by mistake.
 *
 * || Nadie cambia el propio. No contra un ataque —un administrador que quiere
 * hacerse daño ya puede— sino contra el accidente: la fila de uno es la que
 * está más a mano. Y de paso, promoverse solo deja de ser posible aunque
 * mañana `/users` se abriera por error.
 */
export function refuseRoleChange(
  actorId: string,
  target: TargetAccount,
  nextRole: Role,
  otherEnabledAdmins: number,
): Refusal {
  if (actorId === target.id) {
    return "No podés cambiar tu propio rol. Pedíselo a otro administrador."
  }
  if (target.role === nextRole) return null
  return refuseIfLastAdmin(target, otherEnabledAdmins, "degradar")
}

export function refuseDisable(
  target: TargetAccount,
  otherEnabledAdmins: number,
): Refusal {
  if (target.disabledAt) return null
  return refuseIfLastAdmin(target, otherEnabledAdmins, "deshabilitar")
}

export function refuseDelete(
  actorId: string,
  target: TargetAccount,
  otherEnabledAdmins: number,
): Refusal {
  if (actorId === target.id) {
    return "No podés borrar tu propia cuenta. Pedíselo a otro administrador."
  }
  return refuseIfLastAdmin(target, otherEnabledAdmins, "borrar")
}

/**
 * The rule underneath the three above: the console cannot be left with nobody
 * who can administer it.
 *
 * Without it, one click makes `/users`, `/models`, `/agents` and `/corpus`
 * unreachable for everyone, and the only way back is `pnpm seed:admin` from a
 * machine that has the database URL.
 *
 * ``otherEnabledAdmins`` counts enabled administrators OTHER than the target,
 * and the caller has to have counted it **inside the same transaction** as
 * the write. Counting first and writing after is a race: two administrators
 * removing their own role at the same time each see one other, and the result
 * is zero.
 *
 * || La regla de abajo de las tres: la consola no puede quedarse sin nadie
 * que la administre. ``otherEnabledAdmins`` cuenta administradores
 * habilitados DISTINTOS del objetivo, y quien llama tiene que haberlo contado
 * DENTRO de la misma transacción que la escritura: contar antes y escribir
 * después es una condición de carrera, y con dos administradores sacándose el
 * rol a la vez el resultado es cero.
 */
function refuseIfLastAdmin(
  target: TargetAccount,
  otherEnabledAdmins: number,
  verb: string,
): Refusal {
  const targetIsEnabledAdmin =
    target.role === "administrador" && target.disabledAt === null
  if (!targetIsEnabledAdmin) return null
  if (otherEnabledAdmins > 0) return null

  return (
    `No se puede ${verb} al último administrador habilitado: la consola ` +
    "quedaría sin nadie que pueda configurarla."
  )
}

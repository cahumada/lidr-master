"use server"

import { revalidatePath } from "next/cache"

import { auth } from "@/auth"
import {
  refuseDelete,
  refuseDisable,
  refuseRoleChange,
  type TargetAccount,
} from "@/lib/auth/guards"
import { prisma } from "@/lib/auth/prisma"
import { asRole, type Role } from "@/lib/auth/roles"

/**
 * The operations of `/users`.
 *
 * Every one re-checks the caller's role. A Server Action is an endpoint —
 * Next gives it a URL and anyone can POST to it — so the fact that the button
 * lives on an admin-only screen is not what protects it. The layout of
 * `(admin)` guards the *page*; these guard themselves.
 *
 * Every one also re-reads the target and counts the other administrators
 * **inside the transaction that writes**. Counting first and writing after is
 * a race, and the case it loses is the expensive one: two administrators
 * removing their own role at the same time each see the other, both pass, and
 * the console is left with none.
 *
 * || Las cuatro operaciones de `/users`. Cada una revalida el rol de quien
 * llama: una Server Action es un endpoint con URL propia, así que el botón
 * estando en una pantalla de administración no es lo que la protege. Y cada
 * una relee el objetivo y cuenta a los otros administradores DENTRO de la
 * transacción que escribe: contar antes y escribir después es una carrera, y
 * el caso que pierde es el caro — dos administradores sacándose el rol a la
 * vez, cada uno ve al otro, los dos pasan, y la consola queda sin ninguno.
 */

export type ActionResult = { error?: string }

const NOT_ALLOWED = "No tenés permiso para esto."
const GONE = "Esa cuenta ya no existe."

/**
 * Resolves the caller and refuses anyone who is not an administrator.
 * || Resuelve quién llama y rechaza a quien no sea administrador.
 */
async function requireAdmin(): Promise<
  { id: string } | { error: string }
> {
  const session = await auth()
  if (!session?.user?.id) return { error: NOT_ALLOWED }
  if (asRole(session.user.role) !== "administrador") {
    return { error: NOT_ALLOWED }
  }
  return { id: session.user.id }
}

/**
 * Everything the guards need about the target, plus how many OTHER enabled
 * administrators exist. Read inside the caller's transaction.
 * || Todo lo que las barandas necesitan del objetivo, más cuántos OTROS
 * administradores habilitados hay. Leído dentro de la transacción de quien
 * llama.
 */
async function loadTarget(
  tx: Pick<typeof prisma, "user">,
  id: string,
): Promise<{ target: TargetAccount; otherEnabledAdmins: number } | null> {
  const target = await tx.user.findUnique({
    where: { id },
    select: { id: true, role: true, disabledAt: true },
  })
  if (!target) return null

  const otherEnabledAdmins = await tx.user.count({
    where: { role: "administrador", disabledAt: null, id: { not: id } },
  })
  return { target, otherEnabledAdmins }
}

export async function setRole(
  userId: string,
  nextRole: Role,
): Promise<ActionResult> {
  const actor = await requireAdmin()
  if ("error" in actor) return actor

  const result = await prisma.$transaction(async (tx) => {
    const loaded = await loadTarget(tx, userId)
    if (!loaded) return { error: GONE }

    const refusal = refuseRoleChange(
      actor.id,
      loaded.target,
      nextRole,
      loaded.otherEnabledAdmins,
    )
    if (refusal) return { error: refusal }

    await tx.user.update({ where: { id: userId }, data: { role: nextRole } })
    return {}
  })

  revalidatePath("/users")
  return result
}

export async function setEnabled(
  userId: string,
  enabled: boolean,
): Promise<ActionResult> {
  const actor = await requireAdmin()
  if ("error" in actor) return actor

  const result = await prisma.$transaction(async (tx) => {
    const loaded = await loadTarget(tx, userId)
    if (!loaded) return { error: GONE }

    if (!enabled) {
      const refusal = refuseDisable(loaded.target, loaded.otherEnabledAdmins)
      if (refusal) return { error: refusal }
    }

    await tx.user.update({
      where: { id: userId },
      data: { disabledAt: enabled ? null : new Date() },
    })
    return {}
  })

  revalidatePath("/users")
  return result
}

export async function deleteUser(userId: string): Promise<ActionResult> {
  const actor = await requireAdmin()
  if ("error" in actor) return actor

  const result = await prisma.$transaction(async (tx) => {
    const loaded = await loadTarget(tx, userId)
    if (!loaded) return { error: GONE }

    const refusal = refuseDelete(
      actor.id,
      loaded.target,
      loaded.otherEnabledAdmins,
    )
    if (refusal) return { error: refusal }

    // `Account` rows go with it: the relation is `onDelete: Cascade` in the
    // schema, so the linked Google identity does not outlive the user it
    // pointed at.
    // || Las filas de `Account` se van con ella: la relación es
    // `onDelete: Cascade`.
    await tx.user.delete({ where: { id: userId } })
    return {}
  })

  revalidatePath("/users")
  return result
}

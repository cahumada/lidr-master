import { createInterface } from "node:readline/promises"
import { stdin, stdout } from "node:process"

// FIRST, and the order is load-bearing — see the module's own comment.
// || PRIMERO, y el orden importa — ver el comentario del propio módulo.
import "./load-env"

import { hashPassword } from "../lib/auth/password"
import { prisma } from "../lib/auth/prisma-client"

/**
 * Creates or promotes the first administrator, from a machine that already
 * has the database URL.
 *
 * This script exists because `auth.ts` refuses to provision accounts: a
 * Google sign-in for an unknown email is rejected rather than created. That
 * closes the "whoever finds the URL first becomes admin" hole and opens a
 * smaller one — with an empty table, nobody can get in at all. So the first
 * row is seeded by a person who already has database access, which is an
 * ability they had regardless of this console.
 *
 * Run it with:
 *
 *   pnpm seed:admin ada@example.com
 *
 * The password is read from the terminal, never from an argument: an argument
 * lands in the shell history and in the process list, where anyone on the box
 * can read it.
 *
 * || Crea o promueve al primer administrador, desde una máquina que ya tiene
 * la URL de la base. Existe porque `auth.ts` no autoprovisiona: un login de
 * Google con email desconocido se rechaza. Eso cierra el agujero de «el
 * primero que encuentra la URL se hace admin» y abre uno más chico —con la
 * tabla vacía no entra nadie—, así que la primera fila la siembra alguien que
 * ya tiene acceso a la base. La contraseña se lee de la terminal y nunca de
 * un argumento: un argumento queda en el historial del shell y en la lista de
 * procesos.
 */

async function main(): Promise<void> {
  const email = process.argv[2]?.trim().toLowerCase()
  if (!email || !email.includes("@")) {
    console.error("Uso: pnpm seed:admin <email>")
    process.exitCode = 1
    return
  }

  const rl = createInterface({ input: stdin, output: stdout })
  // No masking: `readline` cannot hide input without taking over the tty, and
  // a half-working mask is worse than an honest echo on a script run by one
  // person on their own machine.
  // || Sin enmascarar: `readline` no puede ocultar la entrada sin tomar la
  // tty, y una máscara a medias es peor que un eco honesto.
  const password = (
    await rl.question(`Contraseña para ${email} (se va a ver): `)
  ).trim()
  rl.close()

  if (password.length < 12) {
    console.error(
      "La contraseña tiene que tener al menos 12 caracteres. " +
        "Es la única cuenta que puede cambiar credenciales de proveedores.",
    )
    process.exitCode = 1
    return
  }

  const passwordHash = await hashPassword(password)

  // Upsert and not create: run twice and the second run resets the password
  // and re-promotes, instead of failing on the unique index. Recovering a
  // locked-out administrator is the same operation as creating one.
  // || Upsert y no create: correrlo dos veces resetea la contraseña y vuelve
  // a promover, en vez de fallar por el índice único. Recuperar a un
  // administrador bloqueado es la misma operación que crearlo.
  const user = await prisma.user.upsert({
    where: { email },
    update: { passwordHash, role: "administrador" },
    create: { email, passwordHash, role: "administrador" },
  })

  console.log(`Listo: ${user.email} es administrador (id ${user.id}).`)
}

main()
  .catch((error: unknown) => {
    console.error(error)
    process.exitCode = 1
  })
  .finally(() => prisma.$disconnect())

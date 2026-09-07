"use server"

import { redirect } from "next/navigation"

import { signIn } from "@/auth"
import { hashPassword } from "@/lib/auth/password"
import { prisma } from "@/lib/auth/prisma"

/**
 * Self-registration. Creates the row and stops there — the account is born
 * disabled and an administrator enables it from `/users`.
 *
 * There is deliberately no sign-in afterwards. Signing someone in and then
 * bouncing them off every page would be a worse version of telling them to
 * wait.
 *
 * || Autoregistro. Crea la fila y para: la cuenta nace deshabilitada y un
 * administrador la habilita desde `/users`. A propósito no inicia sesión
 * después — loguear a alguien y después rebotarlo de todas las páginas sería
 * una versión peor de decirle que espere.
 */

export type RegisterState = { error?: string }

const MIN_PASSWORD = 12

export async function register(
  _prev: RegisterState,
  formData: FormData,
): Promise<RegisterState> {
  const email = String(formData.get("email") ?? "")
    .trim()
    .toLowerCase()
  const name = String(formData.get("name") ?? "").trim()
  const password = String(formData.get("password") ?? "")

  if (!email.includes("@")) return { error: "Ese email no parece un email." }
  if (password.length < MIN_PASSWORD) {
    return {
      error: `La contraseña tiene que tener al menos ${MIN_PASSWORD} caracteres.`,
    }
  }

  const passwordHash = await hashPassword(password)

  // The same outcome whether or not the address is taken. Saying "that email
  // is already registered" would turn this form into the account enumerator
  // that `authorize()` in `auth.ts` is careful not to be — the two have to
  // agree or the stricter one is decoration.
  //
  // `create` inside a try instead of an upsert, because an upsert would
  // overwrite the password of an account that already exists. Anyone could
  // reset a stranger's password by "registering" as them.
  //
  // || El mismo desenlace exista o no la dirección. Decir «ese email ya está
  // registrado» convertiría este formulario en el enumerador de cuentas que
  // `authorize()` se cuida de no ser, y si los dos no coinciden, el estricto
  // es decoración. `create` dentro de un try y no un upsert: un upsert
  // pisaría la contraseña de una cuenta existente, y entonces cualquiera
  // reseteraría la contraseña ajena «registrándose» como esa persona.
  try {
    await prisma.user.create({
      data: {
        email,
        name: name || null,
        passwordHash,
        // Not the column's default, and that is on purpose — see the schema.
        // || No es el default de la columna, y es a propósito.
        disabledAt: new Date(),
      },
    })
  } catch (error) {
    // ONLY the unique violation on `email`, and the narrowness is the point.
    //
    // This catch was `catch {}` for about an hour and it cost a debugging
    // session: a stale generated client rejected `disabledAt`, the error went
    // into the void, and the screen cheerfully said the account was pending.
    // A swallow wide enough to hide a schema mismatch is not error handling,
    // it is a lie with good manners.
    //
    // P2002 is Prisma's "unique constraint failed". Matched on the code
    // rather than the error class so this does not couple to where Prisma 7
    // exports it from.
    //
    // || SOLO la violación del único de `email`, y lo angosto es el punto.
    // Este catch fue `catch {}` durante una hora y costó una sesión de
    // depuración: un cliente generado viejo rechazó `disabledAt`, el error se
    // fue al vacío, y la pantalla dijo alegremente que la cuenta quedaba
    // pendiente. Un swallow lo bastante ancho como para tapar un desajuste de
    // esquema no es manejo de errores: es una mentira con buenos modales.
    const code = (error as { code?: unknown } | null)?.code
    if (code !== "P2002") throw error
  }

  redirect("/register/pending")
}

/**
 * Registering with Google is the same act as signing in with it: the callback
 * in `auth.ts` creates the account disabled when the email is unknown. The
 * only difference is where the person lands afterwards, and that is what this
 * `redirectTo` buys — the screen that explains the wait, instead of a login
 * form that just did not work.
 *
 * || Registrarse con Google es el mismo acto que entrar con Google: el
 * callback de `auth.ts` crea la cuenta deshabilitada si el email es
 * desconocido. Lo único que cambia es a dónde aterriza la persona, y eso es
 * lo que compra este `redirectTo`.
 */
export async function registerWithGoogle(): Promise<void> {
  await signIn("google", { redirectTo: "/register/pending" })
}

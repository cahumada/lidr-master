import { PrismaAdapter } from "@auth/prisma-adapter"
import NextAuth from "next-auth"
import type { Adapter } from "next-auth/adapters"
import Credentials from "next-auth/providers/credentials"
import Google from "next-auth/providers/google"

import { verifyPassword } from "@/lib/auth/password"
import { prisma } from "@/lib/auth/prisma"
import { asRole, type Role } from "@/lib/auth/roles"

/**
 * Auth.js for the console: Google and email + password, two roles.
 *
 * Anyone may create their own account, by either method. What nobody may do
 * is *use* it: a new account is born disabled and an administrator enables it
 * from `/users`. That split is the whole shape of this file — see
 * `openspec/changes/add-console-authentication/design.md` §4 for why it is
 * neither "administrators create the accounts" (which meant one person typing
 * another's password) nor open registration (which would open `/answer`, on a
 * public URL, to anyone with a Google account).
 *
 * || Auth.js de la consola: Google y email + contraseña, dos roles.
 * Cualquiera crea su cuenta; nadie la usa hasta que un administrador la
 * habilita. Ese corte es la forma entera de este archivo.
 */

declare module "next-auth" {
  interface Session {
    user: {
      id: string
      role: Role
      name?: string | null
      email?: string | null
      image?: string | null
    }
  }
}

/**
 * The adapter, with `createUser` wrapped so a Google sign-up is born
 * disabled.
 *
 * It has to be here and not in the schema's default. The column defaults to
 * enabled on purpose — that is what the rows predating the column need, the
 * seeded administrator among them — so "new accounts start disabled" is a
 * rule about creation, and this is where Auth.js creates.
 *
 * Wrapping and not reimplementing: everything else about provisioning and
 * account linking stays the adapter's business, and `handleLoginOrRegister`
 * throws `OAuthAccountNotLinked` if a user row exists with no linked
 * `Account`. Pre-creating the row ourselves would walk straight into that.
 *
 * || El adapter, con `createUser` envuelto para que un alta por Google nazca
 * deshabilitada. Va acá y no en el default de la columna: el default es
 * «habilitada» porque es lo que necesitan las filas anteriores a la columna
 * —el administrador sembrado entre ellas—, así que «las cuentas nuevas nacen
 * deshabilitadas» es una regla del alta. Envolver y no reimplementar: crear
 * la fila por nuestra cuenta chocaría con `OAuthAccountNotLinked`.
 */
function identityAdapter(): Adapter {
  const adapter = PrismaAdapter(prisma)
  return {
    ...adapter,
    createUser: (data) =>
      adapter.createUser!({ ...data, disabledAt: new Date() } as typeof data),
  }
}

/**
 * Where a disabled account is sent. A path and not a message, because this is
 * what `callbacks.signIn` returns and Auth.js turns into a redirect.
 * || A dónde va una cuenta deshabilitada.
 */
const DISABLED_REDIRECT = "/login?error=AccountDisabled"

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: identityAdapter(),

  // EXPLICIT, and the single most load-bearing line in this file.
  //
  // `@auth/core` defaults to `strategy: config.adapter ? "database" : "jwt"`
  // (`lib/init.js`), so configuring the adapter above flips the default to
  // `database`. But the credentials branch of the callback action writes a
  // JWT cookie unconditionally, without ever calling the adapter's
  // `createSession`. Left on the default, a password login would set its
  // cookie, raise nothing, and then fail to resolve a session that was never
  // written to the table. Silent logout, no error anywhere.
  //
  // || EXPLÍCITO, y la línea que más carga soporta de este archivo. El
  // default de `@auth/core` pasa a `database` apenas hay adapter, pero la
  // rama de credenciales escribe una cookie JWT igual, sin tocar el adapter.
  // Con el default, el login por contraseña setea la cookie, no lanza nada, y
  // después la sesión no resuelve porque nunca se escribió la fila.
  session: { strategy: "jwt" },

  pages: {
    signIn: "/login",
    error: "/login",
  },

  providers: [
    Google({
      // Always show the account picker. Without this, Google reuses the
      // Gmail session already open in the browser and "create with Google"
      // silently registers whoever was last used — the opposite of choosing.
      // `select_account` and not `consent`: we need the chooser, not a
      // second permission prompt.
      //
      // || Siempre el selector de cuentas. Sin esto, Google reusa la sesión
      // de Gmail que ya está abierta y «crear con Google» registra en
      // silencio a quien se usó la última vez. `select_account` y no
      // `consent`: hace falta el chooser, no otro prompt de permisos.
      authorization: { params: { prompt: "select_account" } },

      // NOT enabled: `allowDangerousEmailAccountLinking`. With
      // self-registration and no email verification of our own, this is not a
      // principle — it is a concrete attack. Someone registers
      // `victim@gmail.com` with a password they choose; later the victim
      // signs in with Google, Auth.js joins the two rows by email address,
      // and the first person — who knows the password — is inside the
      // second's account. That is pre-hijacking, and this flag is what
      // enables it.
      //
      // Off, the second method fails with `OAuthAccountNotLinked` and you
      // sign in the way you registered. Linking both methods is something an
      // administrator does by hand.
      //
      // || NO habilitado. Con autoregistro y sin verificación de email propia
      // esto no es un principio: es un ataque concreto. Alguien registra
      // `victima@gmail.com` con una contraseña que elige; después la víctima
      // entra con Google, Auth.js une las dos filas por el email, y el
      // primero —que sabe la contraseña— queda adentro de la cuenta de la
      // segunda. Es pre-hijacking, y lo habilita esta opción.
      allowDangerousEmailAccountLinking: false,
    }),

    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Contraseña", type: "password" },
      },
      async authorize(credentials) {
        const email = String(credentials?.email ?? "")
          .trim()
          .toLowerCase()
        const password = String(credentials?.password ?? "")
        if (!email || !password) return null

        const user = await prisma.user.findUnique({ where: { email } })

        // One `null` for every failure: unknown email, no password set,
        // wrong password. Telling them apart tells an attacker which half
        // they got right, and turns the login into an account enumerator.
        //
        // Being disabled is NOT one of these. It is decided in the `signIn`
        // callback, after the password has been proved — so the clear message
        // only ever reaches someone who already holds that account's
        // credentials, and tells a stranger nothing.
        //
        // || Un solo `null` para toda falla: email desconocido, cuenta sin
        // contraseña, contraseña incorrecta. Distinguirlas le dice al
        // atacante qué mitad acertó y convierte el login en un enumerador de
        // cuentas. Estar deshabilitada NO es una de estas: se decide en el
        // callback `signIn`, después de probar la contraseña, así que el
        // mensaje claro solo le llega a quien ya tiene esas credenciales.
        if (!user) return null
        if (!(await verifyPassword(password, user.passwordHash))) return null

        // Explicit fields, never the whole row: `user.passwordHash` is on it,
        // and whatever comes out of here reaches the `signIn` callback and
        // the token. `disabledAt` rides along so the gate in `signIn` does
        // not have to query again.
        // || Campos explícitos y nunca la fila entera: `passwordHash` está
        // ahí, y lo que sale de acá llega al callback `signIn` y al token.
        // `disabledAt` viaja para que la compuerta no vuelva a consultar.
        return {
          id: user.id,
          email: user.email,
          name: user.name,
          image: user.image,
          role: user.role,
          disabledAt: user.disabledAt,
        }
      },
    }),
  ],

  callbacks: {
    /**
     * The single gate for "may this person start a session", for BOTH
     * providers — Auth.js runs this callback after `authorize()` for
     * credentials and after the round trip to Google for OAuth, and before
     * either one creates a row.
     *
     * Returning a URL string, rather than `false`, is what lets the login
     * screen say *why*. A `false` becomes `AccessDenied` and loses the
     * distinction between "wrong password" and "your account is waiting for
     * an administrator" — two problems with two different next steps.
     *
     * || La única compuerta de «¿puede abrir sesión?», para los DOS
     * proveedores. Devolver una URL en vez de `false` es lo que le permite al
     * login decir POR QUÉ: un `false` se convierte en `AccessDenied` y pierde
     * la diferencia entre «contraseña incorrecta» y «tu cuenta está esperando
     * que un administrador la habilite» — dos problemas con dos salidas
     * distintas.
     */
    async signIn({ user, account }) {
      if (account?.provider === "credentials") {
        // `authorize()` already proved the password. It hands the row up
        // whole, so the disabled check costs no second query.
        // || `authorize()` ya probó la contraseña y sube la fila entera.
        const disabled = (user as { disabledAt?: Date | null }).disabledAt
        return disabled ? DISABLED_REDIRECT : true
      }

      if (account?.provider !== "google") return true

      const email = user.email?.toLowerCase()
      if (!email) return false

      const existing = await prisma.user.findUnique({
        where: { email },
        select: { disabledAt: true },
      })

      // No row yet: let the adapter create it — disabled, per
      // `identityAdapter` — and let `jwt` below refuse the session it would
      // otherwise mint. Rejecting here instead would mean no account exists
      // for an administrator to enable, which is the opposite of the point.
      //
      // One rough edge, stated rather than hidden: that first attempt lands
      // back on `/login` with no message, because the account did not exist
      // when this ran. The second attempt says it plainly, and `/login`
      // carries a standing note for the first. Closing it properly would mean
      // creating the `Account` row by hand and duplicating adapter internals.
      //
      // || Sin fila todavía: que el adapter la cree —deshabilitada— y que
      // `jwt` niegue la sesión. Rechazar acá dejaría a la persona sin cuenta
      // que un administrador pueda habilitar, que es justo lo contrario. El
      // borde áspero, dicho y no escondido: ese primer intento vuelve a
      // `/login` sin mensaje. El segundo ya lo dice, y `/login` tiene una
      // nota fija para el primero.
      if (!existing) return true

      return existing.disabledAt ? DISABLED_REDIRECT : true
    },

    /**
     * Reads the user row on every session resolution, and returns `null` —
     * which makes `@auth/core` delete the session cookie — when the row is
     * gone or disabled.
     *
     * **This reverses what this file used to say.** The role rode in the
     * token precisely to avoid a query per request, and the comment here
     * accepted the consequence: changing someone's role did not demote them
     * until they renewed. That was tolerable while roles were the only thing
     * that changed.
     *
     * It stopped being tolerable when `/users` gained disable and delete. An
     * account that keeps working until its token expires is not disabled, and
     * a deleted account whose token still resolves is worse. All three
     * operations need to bite on the next request or they are not what the
     * screen claims they are.
     *
     * The price is one indexed lookup per `auth()` call, on an identity table
     * with few rows. The token keeps carrying the role, but now as a cache
     * that the row overrides — never as the authority.
     *
     * || Lee la fila en cada resolución de sesión y devuelve `null` —lo que
     * hace que `@auth/core` borre la cookie— cuando la fila no está o está
     * deshabilitada. **Esto revierte lo que este archivo decía antes**: el rol
     * viajaba en el token justamente para no consultar en cada request, y el
     * comentario aceptaba que cambiar un rol no degradara hasta la renovación.
     * Dejó de ser tolerable cuando `/users` sumó deshabilitar y borrar: una
     * cuenta que sigue funcionando hasta que vence su token no está
     * deshabilitada. El precio es una consulta por índice por cada `auth()`.
     */
    async jwt({ token, user }) {
      if (user) {
        token.sub = user.id
        token.role = asRole((user as { role?: unknown }).role)
        return token
      }

      const id = token.sub
      if (!id) return null

      const row = await prisma.user.findUnique({
        where: { id },
        select: { role: true, disabledAt: true },
      })
      if (!row || row.disabledAt) return null

      token.role = asRole(row.role)
      return token
    },

    async session({ session, token }) {
      session.user.id = String(token.sub ?? "")
      session.user.role = asRole(token.role)
      return session
    },
  },
})

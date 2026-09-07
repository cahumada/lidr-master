import { PageFrame, PageIntro } from "@/components/page-frame"
import { auth } from "@/auth"
import { prisma } from "@/lib/auth/prisma"

import { UsersConsole, type AccountRow } from "./users-console"

export const metadata = {
  title: "Usuarios · Visual Time RAG",
}

/**
 * The account list.
 *
 * The `select` is explicit and short on purpose: `passwordHash` is a column
 * of this table, and a `findMany` with no `select` would carry every hash
 * into a Client Component's props — which is to say, into the HTML. The
 * hash is read here only to derive `hasPassword` and is never passed down.
 *
 * || La lista de cuentas. El `select` es explícito y corto a propósito:
 * `passwordHash` es una columna de esta tabla, y un `findMany` sin `select`
 * arrastraría todos los hashes a las props de un Client Component — o sea, al
 * HTML. El hash se lee acá solo para derivar `hasPassword` y no baja.
 */
export default async function UsersPage() {
  const session = await auth()

  const rows = await prisma.user.findMany({
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      disabledAt: true,
      passwordHash: true,
      createdAt: true,
      accounts: { select: { provider: true } },
    },
    orderBy: [{ disabledAt: "desc" }, { createdAt: "asc" }],
  })

  const accounts: AccountRow[] = rows.map((row) => ({
    id: row.id,
    name: row.name,
    email: row.email,
    role: row.role,
    enabled: row.disabledAt === null,
    createdAt: row.createdAt.toISOString(),
    hasPassword: Boolean(row.passwordHash),
    hasGoogle: row.accounts.some((account) => account.provider === "google"),
  }))

  return (
    <PageFrame>
      <PageIntro title="Usuarios">
        Cualquiera puede registrarse, y nadie entra hasta que alguien de acá lo
        habilite. No se manda ningún mail de verificación, así que la dirección
        es lo que la persona escribió y nada más: habilitá a quien reconozcas,
        no a la dirección. Promover a administrador da acceso a las
        credenciales de proveedores y al rebuild del corpus.
      </PageIntro>
      <UsersConsole accounts={accounts} currentUserId={session?.user?.id ?? ""} />
    </PageFrame>
  )
}

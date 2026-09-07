import { redirect } from "next/navigation"

import { auth } from "@/auth"
import { AppHeader } from "@/components/app-header"
import { prisma } from "@/lib/auth/prisma"
import { AppSidebar } from "@/components/app-sidebar"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"

/**
 * Everything behind a session: the console shell and the gate that resolves
 * it near the data.
 *
 * `proxy.ts` already turned away requests with no session cookie, and this
 * still calls `auth()`. That is not redundancy for its own sake — the proxy
 * *reads* the cookie without verifying its signature, so a forged one gets
 * past the edge on purpose and dies here, where the secret is. Optimistic at
 * the edge, true near the data.
 *
 * The role check is NOT here, and the reason is structural: a layout does not
 * receive the pathname, so deciding by route would mean reading a header the
 * proxy set — and a header is absent exactly when the proxy was skipped,
 * which makes it fail open. The admin routes live under `(admin)/` instead
 * and are gated by that group's own layout, so the protection comes from
 * where a file sits and not from a string comparison that can go missing.
 *
 * || Todo lo que va detrás de una sesión: el shell y el gate que la resuelve
 * cerca de los datos. `proxy.ts` ya rechazó lo que no traía cookie, y acá
 * igual se llama a `auth()`: el proxy LEE la cookie sin verificar su firma,
 * así que una falsificada pasa el borde a propósito y muere acá, donde está
 * el secreto. El chequeo de rol NO está acá y es estructural: un layout no
 * recibe el pathname, y decidir por ruta obligaría a leer un header que puso
 * el proxy — header que falta justo cuando el proxy se saltea, o sea que
 * falla abierto. Las rutas de administración viven bajo `(admin)/` y las
 * cierra el layout de ese grupo.
 */
export default async function ConsoleLayout({ children }: LayoutProps<"/">) {
  const session = await auth()

  // No `next` here: a layout does not know what was asked for. The proxy
  // carries the destination for the common case (no cookie at all); this
  // branch is the rarer one — a cookie that exists and does not resolve.
  // || Sin `next` acá: un layout no sabe qué se pidió. El destino lo lleva el
  // proxy en el caso común; esta rama es la rara — una cookie que existe y no
  // resuelve.
  if (!session?.user) redirect("/login")

  const googleAccount = await prisma.account.findFirst({
    where: { userId: session.user.id, provider: "google" },
    select: { id: true },
  })

  return (
    <SidebarProvider>
      <AppSidebar role={session.user.role} />
      <SidebarInset className="h-svh overflow-hidden">
        <AppHeader
          role={session.user.role}
          name={session.user.name}
          email={session.user.email}
          canLinkGoogle={!googleAccount}
        />
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

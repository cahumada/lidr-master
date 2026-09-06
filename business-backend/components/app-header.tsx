"use client"

import { usePathname } from "next/navigation"
import { LogOut } from "lucide-react"

import { linkOwnGoogle, signOutAction } from "@/app/(console)/actions"
import { Button } from "@/components/ui/button"
import { SidebarTrigger } from "@/components/ui/sidebar"
import type { Role } from "@/lib/auth/roles"
import { CONSOLE_MODULES } from "@/lib/console-nav"

function currentLabel(pathname: string): string {
  if (pathname === "/") return "Inicio"
  for (const navModule of CONSOLE_MODULES) {
    const item = navModule.items.find((entry) => entry.href === pathname)
    if (item) return `${navModule.title} · ${item.title}`
  }
  return "Consola"
}

/**
 * Header: where you are, who you are, and the way out.
 *
 * The label still reads the unfiltered `CONSOLE_MODULES` on purpose. Naming
 * the screen you are on is not the same as offering to take you there, and
 * a `usuario` who reaches `/models` should see the 403 titled, not a header
 * that says "Consola" as if the route were a mystery.
 *
 * Identity comes down as props from `app/(console)/layout.tsx`, which already
 * resolved the session on the server. No `SessionProvider`: a context that
 * re-fetches `/api/auth/session` from the browser would be a second source of
 * truth for something the layout already knows, one render behind.
 *
 * || Header: dónde estás, quién sos y la salida. La etiqueta lee
 * `CONSOLE_MODULES` sin filtrar a propósito: nombrar la pantalla en la que
 * estás no es lo mismo que ofrecerte llevarte, y un `usuario` que llega a
 * `/models` merece ver el 403 con título. La identidad baja por props desde
 * el layout, que ya resolvió la sesión en el servidor. Sin `SessionProvider`:
 * un contexto que re-consulta `/api/auth/session` desde el browser sería una
 * segunda fuente de verdad, siempre un render atrás.
 */
export function AppHeader({
  role,
  name,
  email,
  canLinkGoogle,
}: {
  role: Role
  name?: string | null
  email?: string | null
  canLinkGoogle: boolean
}) {
  const pathname = usePathname()
  const who = name?.trim() || email || "Sesión activa"

  return (
    <header className="border-sidebar-border bg-background sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b px-3">
      <SidebarTrigger />
      <span className="text-muted-foreground truncate text-sm">
        {currentLabel(pathname)}
      </span>

      <div className="ml-auto flex items-center gap-2">
        <span
          className="text-muted-foreground hidden max-w-56 truncate text-xs sm:inline"
          title={email ?? undefined}
        >
          {who}
          {role === "administrador" ? " · admin" : null}
        </span>

        {/* A form and not a link: a GET that signs you out is a GET any page
            can fire at you. || Un form y no un link: un GET que te desloguea
            es un GET que cualquier página te puede disparar. */}
        {canLinkGoogle ? (
          <form action={linkOwnGoogle}>
            <Button
              type="submit"
              variant="outline"
              size="sm"
              title="Tiene que ser la misma cuenta de Google que este email"
            >
              Vincular Google
            </Button>
          </form>
        ) : null}

        <form action={signOutAction}>
          <Button
            type="submit"
            variant="ghost"
            size="icon-sm"
            aria-label="Cerrar sesión"
            title="Cerrar sesión"
          >
            <LogOut />
          </Button>
        </form>
      </div>
    </header>
  )
}

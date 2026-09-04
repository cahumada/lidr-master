"use client"

import { usePathname } from "next/navigation"

import { SidebarTrigger } from "@/components/ui/sidebar"
import { CONSOLE_MODULES } from "@/lib/console-nav"

function currentLabel(pathname: string): string {
  if (pathname === "/") return "Inicio"
  for (const navModule of CONSOLE_MODULES) {
    const item = navModule.items.find((entry) => entry.href === pathname)
    if (item) return `${navModule.title} · ${item.title}`
  }
  return "Consola"
}

export function AppHeader() {
  const pathname = usePathname()

  return (
    <header className="border-sidebar-border bg-background sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b px-3">
      <SidebarTrigger />
      <span className="text-muted-foreground truncate text-sm">
        {currentLabel(pathname)}
      </span>
    </header>
  )
}

"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { ThemeToggle } from "@/components/theme-toggle"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar"
import { CONSOLE_MODULES } from "@/lib/console-nav"

/**
 * Module sidebar. Tokens come from `--sidebar-*` in the Woken theme, so
 * light and dark stay in sync without a color written here.
 * || Sidebar por módulos. Los tokens salen de `--sidebar-*` del tema Woken:
 * claro y oscuro se mantienen alineados sin un color escrito acá.
 */
export function AppSidebar() {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              render={<Link href="/" />}
              isActive={pathname === "/"}
              tooltip="Inicio"
              size="lg"
            >
              <span className="flex flex-col leading-tight">
                <span className="text-sm font-semibold tracking-tight">
                  Visual Time
                </span>
                <span className="text-sidebar-foreground/70 text-xs">RAG</span>
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {CONSOLE_MODULES.map((module) => (
          <SidebarGroup key={module.id}>
            <SidebarGroupLabel>{module.title}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {module.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <SidebarMenuItem key={item.href}>
                      <SidebarMenuButton
                        render={<Link href={item.href} />}
                        isActive={pathname === item.href}
                        tooltip={item.title}
                      >
                        <Icon />
                        <span>{item.title}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarSeparator />
      <SidebarFooter>
        <div className="flex items-center justify-between px-1 group-data-[collapsible=icon]:justify-center">
          <span className="text-sidebar-foreground/70 px-1 text-xs group-data-[collapsible=icon]:hidden">
            Tema
          </span>
          <ThemeToggle />
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}

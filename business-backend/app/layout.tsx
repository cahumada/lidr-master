import type { Metadata } from "next"

import { AppHeader } from "@/components/app-header"
import { AppSidebar } from "@/components/app-sidebar"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { THEME_INIT_SCRIPT } from "@/lib/theme"
import "./globals.css"

export const metadata: Metadata = {
  title: "Visual Time RAG",
  description:
    "Consola del RAG sobre la documentación funcional de Visual Time.",
}

/**
 * No `next/font` here: the "Woken" theme brings its own font stacks
 * (`--font-sans`, `--font-mono` in `globals.css`), all of them system fonts.
 * Loading a webfont on top would download bytes that nothing renders.
 *
 * || Sin `next/font` acá: el tema "Woken" trae sus propias pilas tipográficas
 * (`--font-sans`, `--font-mono` en `globals.css`), todas fuentes del sistema.
 * Cargar una webfont encima sería bajar bytes que después nada usa.
 */
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // No `className` on `<html>`: React owns that prop and, on hydrate, resets
    // the attribute to exactly what JSX says — wiping the `dark` class the
    // inline script and the toggle add via `classList`. Base styles live in
    // `globals.css`; only the theme class is touched imperatively.
    // || Sin `className` en `<html>`: React es dueño de esa prop y, al
    // hidratar, deja el atributo exactamente como dice el JSX — borrando la
    // clase `dark` que el script inline y el toggle agregan con `classList`.
    // Los estilos base viven en `globals.css`; solo la clase de tema se toca
    // de forma imperativa.
    //
    // `suppressHydrationWarning`: the inline script may add `dark` before
    // hydration, so the DOM can legitimately differ from the server output.
    // || `suppressHydrationWarning`: el script inline puede agregar `dark`
    // antes de la hidratación, así que el DOM puede diferir del HTML del servidor.
    <html lang="es" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="bg-background text-foreground min-h-full">
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset className="overflow-hidden">
            <AppHeader />
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              {children}
            </div>
          </SidebarInset>
        </SidebarProvider>
      </body>
    </html>
  )
}

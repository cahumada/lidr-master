import type { Metadata } from "next"

import { ThemeFavicon } from "@/components/theme-favicon"
import { THEME_INIT_SCRIPT } from "@/lib/theme"
import "./globals.css"

export const metadata: Metadata = {
  title: "Visual Time RAG",
  description:
    "Consola del RAG sobre la documentación funcional de Visual Time.",
  icons: {
    icon: { url: "/brand/logotipo2-negativo.png", type: "image/png" },
  },
}

/**
 * Document shell only: `<html>`, `<body>`, the theme script.
 *
 * The console chrome — sidebar, header — used to live here and moved to
 * `app/(console)/layout.tsx`. It had to: `/login` renders before there is a
 * session, and a sidebar of screens you cannot open yet is both wrong and a
 * leak of what exists. What stays here is what every page needs, signed in or
 * not, and the theme is exactly that.
 *
 * No `next/font`: the "Woken" theme brings its own font stacks
 * (`--font-sans`, `--font-mono` in `globals.css`), all of them system fonts.
 * Loading a webfont on top would download bytes that nothing renders.
 *
 * || Solo el shell del documento. El chrome de la consola —sidebar, header—
 * vivía acá y se mudó a `app/(console)/layout.tsx`: `/login` se renderiza
 * antes de que haya sesión, y un sidebar de pantallas que todavía no se
 * pueden abrir está mal y además cuenta qué existe. Acá queda lo que toda
 * página necesita, con sesión o sin ella.
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
        <ThemeFavicon />
        {children}
      </body>
    </html>
  )
}

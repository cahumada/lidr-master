import type { Metadata } from "next";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: "Visual Time RAG",
  description:
    "Consola del RAG sobre la documentación funcional de Visual Time.",
};

const NAV = [
  { href: "/search", label: "Búsqueda" },
  { href: "/documents", label: "Ingesta" },
  { href: "/corpus", label: "Corpus" },
];

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
      <body className="bg-background text-foreground flex min-h-full flex-col">
        <header className="border-b">
          <nav className="mx-auto flex w-full max-w-6xl items-center gap-6 px-6 py-3">
            <Link href="/" className="text-sm font-semibold tracking-tight">
              Visual Time <span className="text-muted-foreground">RAG</span>
            </Link>
            <div className="flex items-center gap-1">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-muted-foreground hover:text-foreground rounded-md px-3 py-1.5 text-sm transition-colors"
                >
                  {item.label}
                </Link>
              ))}
            </div>
            <div className="ml-auto">
              <ThemeToggle />
            </div>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}

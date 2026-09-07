/**
 * The shell for screens that render before there is a session.
 *
 * No sidebar and no header on purpose. Beyond the obvious — the links would
 * not work — a navigation listing `/corpus` and `/models` to someone who has
 * not signed in tells them what this console operates. Cheap to withhold.
 *
 * || El shell de las pantallas que se renderizan antes de que haya sesión.
 * Sin sidebar y sin header a propósito: además de que los links no andarían,
 * una navegación que lista `/corpus` y `/models` a quien no entró le cuenta
 * qué opera esta consola. Barato no decirlo.
 */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex min-h-dvh items-center justify-center px-6 py-12">
      {children}
    </main>
  )
}

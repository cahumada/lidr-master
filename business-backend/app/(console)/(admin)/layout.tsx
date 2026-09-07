import { auth } from "@/auth"
import { ForbiddenScreen } from "@/components/forbidden-screen"

/**
 * The gate for the screens that write configuration or destroy data:
 * `/agents`, `/agents/flow`, `/models`, `/corpus`.
 *
 * Membership is the file system, not a list of paths. A screen is protected
 * because it sits under this directory, so moving one in or out of the group
 * is the whole change and there is no table to forget to update. The paths
 * are still enumerated once, in `lib/auth/roles.ts`, for the navigation to
 * filter by — and that copy is presentation only: deleting it hides nothing
 * and opens nothing, because this layout is what actually refuses.
 *
 * Renders the refusal rather than calling `forbidden()`: that API needs
 * `experimental.authInterrupts`, and this change already leans on Auth.js
 * beta plus an adapter that does not declare Prisma 7. Consequence, stated
 * where it is paid: the screen says 403, the HTTP status is 200. It is the
 * user-visible half of the requirement; the status code needs that flag.
 *
 * || El gate de las pantallas que escriben configuración o destruyen datos.
 * La pertenencia es el file system y no una lista de rutas: una pantalla está
 * protegida porque está en este directorio. Las rutas se enumeran igual en
 * `lib/auth/roles.ts` para que la navegación filtre, y esa copia es solo
 * presentación — borrarla no oculta ni abre nada, porque el que rechaza es
 * este layout. Se renderiza el rechazo en vez de llamar a `forbidden()`, que
 * exige un flag experimental. La consecuencia, dicha donde se paga: la
 * pantalla dice 403, el status HTTP es 200.
 */
export default async function AdminLayout({ children }: LayoutProps<"/">) {
  const session = await auth()

  // Not `!== "administrador"` on a value that could be undefined: `asRole`
  // already floored whatever came out of the token to a known role in
  // `auth.ts`, so this compares two roles and nothing else.
  // || El rol ya vino aterrizado por `asRole` en `auth.ts`, así que acá se
  // comparan dos roles y nada más.
  if (session?.user?.role !== "administrador") {
    return <ForbiddenScreen />
  }

  return children
}

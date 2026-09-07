import Link from "next/link"
import { ShieldOff } from "lucide-react"

import { PageFrame } from "@/components/page-frame"
import { Button } from "@/components/ui/button"

/**
 * What a session without the role sees instead of an admin screen.
 *
 * It says the screen exists and that the account lacks the permission —
 * deliberately, and not a 404. Hiding the route stops nobody who already
 * knows it is there (the repo is public and the paths are in it), and it
 * strands the person who legitimately needs the permission with no idea what
 * to ask for or of whom.
 *
 * It keeps the console shell around it: someone who lands here is signed in
 * and the sidebar is the way out.
 *
 * || Lo que ve una sesión sin el rol. Dice que la pantalla existe y que a la
 * cuenta le falta el permiso, a propósito y no un 404: esconder la ruta no
 * detiene a quien ya sabe que existe —el repo es público y las rutas están
 * ahí— y sí deja varado a quien legítimamente necesita el permiso, sin saber
 * qué pedir ni a quién. Conserva el shell: quien cae acá tiene sesión y el
 * sidebar es la salida.
 */
export function ForbiddenScreen() {
  return (
    <PageFrame>
      <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-16 text-center">
        <div className="bg-muted text-muted-foreground rounded-full p-3">
          <ShieldOff className="size-6" aria-hidden />
        </div>

        <div>
          <p className="text-muted-foreground text-xs font-medium tracking-widest uppercase">
            403
          </p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">
            No tenés permiso para esta pantalla
          </h1>
          <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
            Esta sección configura cómo responde el sistema o reconstruye el
            corpus, así que pide el rol <code>administrador</code>. Tu cuenta
            entra como <code>usuario</code>. Un administrador puede cambiártelo.
          </p>
        </div>

        <Button render={<Link href="/" />} variant="outline" size="sm">
          Volver a la portada
        </Button>
      </div>
    </PageFrame>
  )
}

import type { Metadata } from "next"
import Link from "next/link"
import { Clock } from "lucide-react"

import { Button } from "@/components/ui/button"

export const metadata: Metadata = {
  title: "Cuenta pendiente · Visual Time RAG",
}

/**
 * Where both registration paths land: the form's `redirect()` and the
 * `redirectTo` of the Google button.
 *
 * It says the same thing whether or not an account was actually created. That
 * is not vagueness — it is the enumeration rule from `actions.ts` carried
 * through to the screen. A page that said "created!" versus "that email
 * already exists" would give away, to anyone with a browser, which addresses
 * are registered.
 *
 * || Donde aterrizan los dos caminos del registro. Dice lo mismo se haya
 * creado la cuenta o no, y eso no es vaguedad: es la regla de enumeración de
 * `actions.ts` llevada hasta la pantalla. Una página que dijera «¡creada!» o
 * «ese email ya existe» le regalaría a cualquiera con un browser la lista de
 * direcciones registradas.
 */
export default function RegisterPendingPage() {
  return (
    <div className="flex w-full max-w-sm flex-col items-center gap-5 text-center">
      <div className="bg-muted text-muted-foreground rounded-full p-3">
        <Clock className="size-6" aria-hidden />
      </div>

      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          Tu cuenta quedó pendiente
        </h1>
        <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
          Un administrador tiene que habilitarla antes de que puedas entrar. No
          te vamos a mandar ningún mail cuando pase, así que avisale vos que te
          registraste.
        </p>
      </div>

      <Button render={<Link href="/login" />} variant="outline" size="sm">
        Ir al login
      </Button>
    </div>
  )
}

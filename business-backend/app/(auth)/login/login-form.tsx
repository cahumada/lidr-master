"use client"

import Link from "next/link"
import { useActionState } from "react"
import { AlertCircle } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"

import {
  signInWithGoogle,
  signInWithPassword,
  type LoginState,
} from "./actions"

/**
 * The sign-in form. Client only because it needs `useActionState` for the
 * pending state and the error — the credentials it collects never leave the
 * server action.
 *
 * || El formulario. De cliente solo porque necesita `useActionState` para el
 * estado de envío y el error; las credenciales que junta no salen de la
 * Server Action.
 */
export function LoginForm({
  next,
  initialError,
  hideGoogle,
}: {
  next: string
  initialError?: string
  hideGoogle?: boolean
}) {
  const [state, formAction, pending] = useActionState<LoginState, FormData>(
    signInWithPassword,
    {},
  )

  // The action's error wins once there is one: it describes what just
  // happened, while `initialError` describes how the user arrived.
  // || El error de la acción gana apenas existe: describe lo que acaba de
  // pasar, mientras que `initialError` describe cómo llegó el usuario.
  const error = state.error ?? initialError

  return (
    <div className="flex w-full max-w-sm flex-col gap-6">
      <div className="flex flex-col gap-1 text-center">
        <h1 className="text-xl font-semibold tracking-tight">
          Consola del RAG de Visual Time
        </h1>
        <p className="text-muted-foreground text-sm">
          Entrá para operar el corpus y consultar la documentación.
        </p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {hideGoogle ? null : (
        <>
          <form action={signInWithGoogle}>
            <input type="hidden" name="next" value={next} />
            <Button type="submit" variant="outline" size="lg" className="w-full">
              Entrar con Google
            </Button>
          </form>

          <div className="flex items-center gap-3">
            <Separator className="flex-1" />
            <span className="text-muted-foreground text-xs">o</span>
            <Separator className="flex-1" />
          </div>
        </>
      )}

      <form action={formAction} className="flex flex-col gap-4">
        <input type="hidden" name="next" value={next} />

        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Contraseña</Label>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </div>

        <Button type="submit" size="lg" disabled={pending} className="w-full">
          {pending ? "Entrando…" : "Entrar"}
        </Button>
      </form>

      {/* The standing note covers the one gap the error codes cannot: a first
          Google sign-in with an unknown email creates the account and bounces
          back here with nothing in the URL, because the account did not exist
          when the callback ran. See `auth.ts`, callback `signIn`.
          || La nota fija cubre el único hueco que los códigos de error no
          pueden: un primer login con Google de un email desconocido crea la
          cuenta y vuelve acá sin nada en la URL. */}
      <p className="text-muted-foreground text-center text-xs leading-relaxed">
        ¿Te registraste recién? Tu cuenta queda pendiente hasta que un
        administrador la habilite.
      </p>

      <p className="text-center text-xs">
        <Link href="/register" className="underline underline-offset-4">
          Crear una cuenta
        </Link>
      </p>
    </div>
  )
}

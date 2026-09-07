"use client"

import Link from "next/link"
import { useActionState } from "react"
import { AlertCircle } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"

import { register, registerWithGoogle, type RegisterState } from "./actions"

export function RegisterForm() {
  const [state, formAction, pending] = useActionState<RegisterState, FormData>(
    register,
    {},
  )

  return (
    <div className="flex w-full max-w-sm flex-col gap-6">
      <div className="flex flex-col gap-1 text-center">
        <h1 className="text-xl font-semibold tracking-tight">Crear cuenta</h1>
        <p className="text-muted-foreground text-sm">
          La cuenta queda pendiente hasta que un administrador la habilite.
        </p>
      </div>

      {state.error ? (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      ) : null}

      <form action={registerWithGoogle}>
        <Button type="submit" variant="outline" size="lg" className="w-full">
          Registrarme con Google
        </Button>
      </form>

      <div className="flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="text-muted-foreground text-xs">o</span>
        <Separator className="flex-1" />
      </div>

      <form action={formAction} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="name">Nombre</Label>
          <Input id="name" name="name" autoComplete="name" />
        </div>

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
            autoComplete="new-password"
            minLength={12}
            required
          />
          <p className="text-muted-foreground text-xs">Mínimo 12 caracteres.</p>
        </div>

        <Button type="submit" size="lg" disabled={pending} className="w-full">
          {pending ? "Creando…" : "Crear cuenta"}
        </Button>
      </form>

      {/* Said here and not only on the pending screen: it changes whether
          someone bothers to register at all. || Dicho acá y no solo en la
          pantalla de espera: cambia si la persona se registra o no. */}
      <p className="text-muted-foreground text-center text-xs leading-relaxed">
        No mandamos ningún mail de confirmación. Quien habilite tu cuenta te
        tiene que conocer, así que avisale por otro lado que te registraste.
      </p>

      <p className="text-center text-xs">
        <Link href="/login" className="underline underline-offset-4">
          Ya tengo cuenta
        </Link>
      </p>
    </div>
  )
}

import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { auth } from "@/auth"

import { RegisterForm } from "./register-form"

export const metadata: Metadata = {
  title: "Crear cuenta · Visual Time RAG",
}

/**
 * Self-registration. Open without a session — `proxy.ts` excludes this path
 * for the same reason it excludes `/login`: needing an account to ask for one
 * is a closed loop.
 *
 * || Autoregistro. Abierta sin sesión — `proxy.ts` excluye esta ruta por lo
 * mismo que excluye `/login`: necesitar cuenta para pedir una es un bucle.
 */
export default async function RegisterPage() {
  const session = await auth()
  if (session?.user) redirect("/")

  return <RegisterForm />
}

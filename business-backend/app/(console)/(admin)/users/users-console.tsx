"use client"

import { useState, useTransition } from "react"
import { AlertCircle, Check, ShieldCheck, Trash2, X } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  refuseDelete,
  refuseDisable,
  refuseRoleChange,
} from "@/lib/auth/guards"
import type { Role } from "@/lib/auth/roles"

import { linkOwnGoogle } from "@/app/(console)/actions"

import { deleteUser, setEnabled, setRole } from "./actions"

export type AccountRow = {
  id: string
  name: string | null
  email: string
  role: Role
  enabled: boolean
  createdAt: string
  hasPassword: boolean
  hasGoogle: boolean
}

function loginMethodLabel(account: AccountRow): string {
  if (account.hasGoogle && account.hasPassword) return "Google y contraseña"
  if (account.hasGoogle) return "Google"
  return "Contraseña"
}

/**
 * The account table.
 *
 * It calls the same `refuse*` functions the Server Actions call, from
 * `lib/auth/guards.ts` — that is why they are pure and live outside both.
 * Here the answer greys out a button and shows why; there it refuses the
 * write. Neither is a copy of the other, so neither can drift.
 *
 * The disabled button is not the protection, and it is worth being blunt
 * about that: a Server Action has its own URL and anyone can POST to it. The
 * button state is a courtesy, the check in `actions.ts` is the rule.
 *
 * || La tabla de cuentas. Llama a las MISMAS funciones `refuse*` que llaman
 * las Server Actions — por eso son puras y viven afuera de las dos. Acá la
 * respuesta apaga un botón y dice por qué; allá rechaza la escritura. Ninguna
 * es copia de la otra, así que no se pueden separar. El botón apagado no es
 * la protección: una Server Action tiene URL propia y cualquiera puede
 * postearle. El botón es cortesía, la regla está en `actions.ts`.
 */
export function UsersConsole({
  accounts,
  currentUserId,
}: {
  accounts: AccountRow[]
  currentUserId: string
}) {
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null)

  const enabledAdmins = accounts.filter(
    (account) => account.role === "administrador" && account.enabled,
  ).length

  function othersFor(account: AccountRow): number {
    const selfCounts = account.role === "administrador" && account.enabled
    return enabledAdmins - (selfCounts ? 1 : 0)
  }

  function run(action: () => Promise<{ error?: string }>) {
    setError(null)
    startTransition(async () => {
      const result = await action()
      if (result.error) setError(result.error)
    })
  }

  return (
    <div className="flex flex-col gap-4">
      {error ? (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Cuenta</TableHead>
            <TableHead>Rol</TableHead>
            <TableHead>Entra con</TableHead>
            <TableHead>Estado</TableHead>
            <TableHead className="text-right">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {accounts.map((account) => {
            const target = {
              id: account.id,
              role: account.role,
              disabledAt: account.enabled ? null : new Date(),
            }
            const others = othersFor(account)
            const nextRole: Role =
              account.role === "administrador" ? "usuario" : "administrador"

            const roleRefusal = refuseRoleChange(
              currentUserId,
              target,
              nextRole,
              others,
            )
            const enableRefusal = account.enabled
              ? refuseDisable(target, others)
              : null
            const deleteRefusal = refuseDelete(currentUserId, target, others)

            return (
              <TableRow key={account.id} data-disabled={!account.enabled}>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium">
                      {account.name?.trim() || "—"}
                      {account.id === currentUserId ? (
                        <span className="text-muted-foreground"> (vos)</span>
                      ) : null}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      {account.email}
                    </span>
                  </div>
                </TableCell>

                <TableCell>
                  <Badge
                    variant={
                      account.role === "administrador" ? "default" : "secondary"
                    }
                  >
                    {account.role}
                  </Badge>
                </TableCell>

                <TableCell className="text-muted-foreground text-xs">
                  {loginMethodLabel(account)}
                </TableCell>

                <TableCell>
                  {account.enabled ? (
                    <Badge variant="outline">habilitada</Badge>
                  ) : (
                    <Badge variant="destructive">pendiente</Badge>
                  )}
                </TableCell>

                <TableCell>
                  <div className="flex items-center justify-end gap-1">
                    {account.id === currentUserId && !account.hasGoogle ? (
                      <form action={linkOwnGoogle}>
                        <Button
                          type="submit"
                          variant="ghost"
                          size="sm"
                          disabled={pending}
                          title="Tiene que ser la misma cuenta de Google que este email"
                        >
                          Vincular Google
                        </Button>
                      </form>
                    ) : null}

                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={pending || roleRefusal !== null}
                      title={roleRefusal ?? `Cambiar a ${nextRole}`}
                      onClick={() => run(() => setRole(account.id, nextRole))}
                    >
                      <ShieldCheck />
                      {nextRole === "administrador" ? "Promover" : "Degradar"}
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={pending || enableRefusal !== null}
                      title={
                        enableRefusal ??
                        (account.enabled ? "Deshabilitar" : "Habilitar")
                      }
                      onClick={() =>
                        run(() => setEnabled(account.id, !account.enabled))
                      }
                    >
                      {account.enabled ? <X /> : <Check />}
                      {account.enabled ? "Deshabilitar" : "Habilitar"}
                    </Button>

                    {/* Two clicks, and no dialog: deleting a row plus its
                        linked Google identity is the one thing on this screen
                        that cannot be undone. || Dos clics y sin diálogo:
                        borrar es lo único de esta pantalla que no se deshace. */}
                    <Button
                      variant={
                        confirmingDelete === account.id ? "destructive" : "ghost"
                      }
                      size="sm"
                      disabled={pending || deleteRefusal !== null}
                      title={deleteRefusal ?? "Borrar"}
                      onClick={() => {
                        if (confirmingDelete !== account.id) {
                          setConfirmingDelete(account.id)
                          return
                        }
                        setConfirmingDelete(null)
                        run(() => deleteUser(account.id))
                      }}
                    >
                      <Trash2 />
                      {confirmingDelete === account.id ? "¿Seguro?" : "Borrar"}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>

      <p className="text-muted-foreground text-xs leading-relaxed">
        Deshabilitar es reversible y conserva el historial de la cuenta; borrar
        elimina la fila y su cuenta de Google vinculada. Los dos tienen efecto
        en la sesión abierta: quien esté adentro queda afuera en su próximo
        request, sin esperar a que venza su token.
      </p>
    </div>
  )
}

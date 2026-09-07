"use client"

import { useState } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { UsageSummary } from "@/lib/ai-service/types"
import { artLocalToIso } from "@/lib/usage-month"

const NUMBER = new Intl.NumberFormat("es-AR")

const PURPOSE_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "answer", label: "Respuesta (answer)" },
  { value: "answer_synthesizer", label: "Sintetizador (answer_synthesizer)" },
] as const

function formatCount(value: number): string {
  return NUMBER.format(value)
}

/**
 * Tenant ledger. Filters are forwarded as-is; an inverted range is a 422
 * from the service, not a silent empty table.
 * || Ledger del tenant. Los filtros viajan tal cual; un rango invertido es
 * un 422 del servicio, no una tabla vacía en silencio.
 */
export function UsageConsole({
  initial,
  loadError,
  initialFrom,
  initialTo,
}: {
  initial: UsageSummary | null
  loadError: string | null
  initialFrom: string
  initialTo: string
}) {
  const [summary, setSummary] = useState<UsageSummary | null>(initial)
  const [error, setError] = useState<string | null>(loadError)
  const [pending, setPending] = useState(false)
  const [fromLocal, setFromLocal] = useState(initialFrom)
  const [toLocal, setToLocal] = useState(initialTo)
  const [purpose, setPurpose] = useState("")
  const [sessionId, setSessionId] = useState("")

  async function apply(event: React.FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)

    const params = new URLSearchParams()
    const from = artLocalToIso(fromLocal)
    const to = artLocalToIso(toLocal)
    if (from) params.set("from", from)
    if (to) params.set("to", to)
    if (purpose) params.set("purpose", purpose)
    const session = sessionId.trim()
    if (session) params.set("session_id", session)
    const suffix = params.size > 0 ? `?${params}` : ""

    try {
      const response = await fetch(`/api/usage/summary${suffix}`)
      const body = (await response.json()) as UsageSummary & { error?: string }
      if (!response.ok) {
        // Keep the last successful totals. A 422 is not an empty ledger.
        // || Conserva los últimos totales. Un 422 no es un ledger vacío.
        setError(body.error ?? "No se pudo leer el uso.")
        return
      }
      setSummary(body)
    } catch {
      setError("No se pudo contactar a la consola.")
    } finally {
      setPending(false)
    }
  }

  const emptyLedger = summary !== null && summary.total_calls === 0

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={apply} className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="usage-from">Desde</Label>
            <Input
              id="usage-from"
              type="datetime-local"
              value={fromLocal}
              onChange={(event) => setFromLocal(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="usage-to">Hasta</Label>
            <Input
              id="usage-to"
              type="datetime-local"
              value={toLocal}
              onChange={(event) => setToLocal(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="usage-purpose">Propósito</Label>
            <select
              id="usage-purpose"
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              className="border-input bg-background h-8 rounded-lg border px-2.5 text-sm"
            >
              {PURPOSE_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="usage-session">Sesión (opcional)</Label>
            <Input
              id="usage-session"
              value={sessionId}
              onChange={(event) => setSessionId(event.target.value)}
              placeholder="session_id"
              autoComplete="off"
            />
          </div>
        </div>
        <div className="flex justify-end">
          <Button type="submit" disabled={pending} aria-busy={pending}>
            {pending ? "Consultando…" : "Aplicar"}
          </Button>
        </div>
      </form>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {summary === null ? null : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Llamadas" value={summary.total_calls} />
            <MetricCard label="Tokens de entrada" value={summary.input_tokens} />
            <MetricCard label="Tokens de salida" value={summary.output_tokens} />
            <MetricCard label="Tokens en total" value={summary.total_tokens} />
          </div>

          {emptyLedger ? (
            <p className="text-muted-foreground text-sm">
              Todavía no hay completions cobradas en este recorte.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Proveedor</TableHead>
                  <TableHead>Modelo</TableHead>
                  <TableHead className="text-right">Llamadas</TableHead>
                  <TableHead className="text-right">Entrada</TableHead>
                  <TableHead className="text-right">Salida</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {summary.by_model.map((row) => (
                  <TableRow key={`${row.provider_id}:${row.model}`}>
                    <TableCell className="font-mono text-xs">{row.provider_id}</TableCell>
                    <TableCell className="font-mono text-xs">{row.model}</TableCell>
                    <TableCell className="text-right">{formatCount(row.calls)}</TableCell>
                    <TableCell className="text-right">
                      {formatCount(row.input_tokens)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCount(row.output_tokens)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCount(row.total_tokens)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="font-mono text-2xl tabular-nums">
          {formatCount(value)}
        </CardTitle>
      </CardHeader>
    </Card>
  )
}

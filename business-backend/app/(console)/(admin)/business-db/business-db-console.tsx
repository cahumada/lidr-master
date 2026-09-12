"use client"

import { useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type {
  ActiveRunInfo,
  CorpusStampInfo,
  ExtractionRunItem,
  ExtractionRunList,
} from "@/lib/ai-service/types"

const DATE = new Intl.DateTimeFormat("es-AR", {
  dateStyle: "short",
  timeStyle: "short",
})

const ORIGIN_LABEL: Record<ActiveRunInfo["origin"], string> = {
  selected: "Elegida",
  default: "Default de configuración",
  none: "Ninguna",
}

function formatWhen(value: string | null): string {
  if (!value) return "—"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return DATE.format(parsed)
}

function shortHash(value: string | null): string {
  if (!value) return "—"
  return value.length > 12 ? `${value.slice(0, 12)}…` : value
}

function LoadFlags({ run }: { run: ExtractionRunItem }) {
  return (
    <div className="flex flex-wrap gap-1">
      <Badge variant={run.loaded_metadata ? "secondary" : "outline"}>
        metadata {run.loaded_metadata ? "sí" : "no"}
      </Badge>
      <Badge variant={run.loaded_dependencies ? "secondary" : "outline"}>
        deps {run.loaded_dependencies ? "sí" : "no"}
      </Badge>
      <Badge variant={run.loaded_data ? "secondary" : "outline"}>
        datos {run.loaded_data ? "sí" : "no"}
      </Badge>
      {/* Absence of the build, not a zero count: a batch that produced nothing
          still ran, and collapsing the two hides a deployment gap.
          || La ausencia del build, no un conteo en cero. */}
      <Badge
        variant={run.tables_built ? "secondary" : "outline"}
        title={
          run.tables_built
            ? `${run.table_edge_count ?? 0} aristas${
                run.tables_built_at ? ` · ${formatWhen(run.tables_built_at)}` : ""
              }`
            : "Corré scripts/build_transaction_tables.py para esta corrida."
        }
      >
        tablas {run.tables_built ? "sí" : "no"}
      </Badge>
    </div>
  )
}

function ActiveSummary({
  active,
  stamp,
}: {
  active: ActiveRunInfo
  stamp: CorpusStampInfo | null
}) {
  const label = active.run_id
    ? `${active.run_id} · ${active.env}`
    : "Sin corrida vigente"

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Corrida en vigor</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono">{label}</span>
          <Badge variant="outline">{ORIGIN_LABEL[active.origin]}</Badge>
          {active.run_id && <Badge>Vigente</Badge>}
        </div>
        {active.reason && active.origin === "none" && (
          <p className="text-muted-foreground">{active.reason}</p>
        )}
        {active.activated_at && (
          <p className="text-muted-foreground">
            Activada {formatWhen(active.activated_at)}
            {active.activated_by ? ` por ${active.activated_by}` : ""}
          </p>
        )}
        {stamp && (
          <p className="text-muted-foreground">
            Sello del corpus: {stamp.run_id} · {stamp.env} (
            {formatWhen(stamp.stamped_at)}, {stamp.rows_updated.toLocaleString("es-AR")}{" "}
            filas)
          </p>
        )}
        {stamp && !stamp.matches_active && (
          <Alert>
            <AlertTitle>Desfasaje con el sello del corpus</AlertTitle>
            <AlertDescription>
              La metadata estampada en los chunks salió de {stamp.run_id} ·{" "}
              {stamp.env}, distinta de la corrida activa. No se corrige solo: hay
              que re-estampar o volver a la corrida del sello.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * Lists every mirror run and activates only those with `loaded_data`.
 * || Lista todas las corridas del mirror y activa solo las que tienen
 * `loaded_data`.
 */
export function BusinessDbConsole({
  initial,
  loadError,
  declaredBy,
}: {
  initial: ExtractionRunList | null
  loadError: string | null
  declaredBy: string | null
}) {
  const [data, setData] = useState<ExtractionRunList | null>(initial)
  const [error, setError] = useState<string | null>(loadError)
  const [pendingRunId, setPendingRunId] = useState<string | null>(null)

  async function refresh() {
    setError(null)
    try {
      const response = await fetch("/api/business-db/runs")
      const body = (await response.json()) as ExtractionRunList & { error?: string }
      if (!response.ok) {
        setError(body.error ?? "No se pudo leer las corridas.")
        return
      }
      setData(body)
    } catch {
      setError("No se pudo contactar a la consola.")
    }
  }

  async function activate(run: ExtractionRunItem) {
    const message =
      `¿Activar la corrida ${run.run_id} (${run.env})?\n\n` +
      "El servicio responderá con el árbol de navegación y el bloque de base " +
      "de esa corrida. Quien opera el producto queda por encima del default " +
      "de despliegue."
    if (!window.confirm(message)) return

    setPendingRunId(run.run_id)
    setError(null)

    const body: { activated_by?: string } = {}
    if (declaredBy) body.activated_by = declaredBy

    try {
      const response = await fetch(
        `/api/business-db/runs/${encodeURIComponent(run.run_id)}/activate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      )
      const payload = (await response.json()) as {
        active?: ActiveRunInfo
        error?: string
      }
      if (!response.ok) {
        setError(payload.error ?? "No se pudo activar la corrida.")
        return
      }
      await refresh()
    } catch {
      setError("No se pudo contactar a la consola.")
    } finally {
      setPendingRunId(null)
    }
  }

  const runs = data?.runs ?? []
  const active = data?.active ?? initial?.active
  const stamp = data?.stamp ?? initial?.stamp ?? null

  return (
    <div className="flex flex-col gap-6">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loadError && !data && (
        <Alert>
          <AlertDescription>
            No se pudo cargar el listado inicial. {loadError}
          </AlertDescription>
        </Alert>
      )}

      {active && <ActiveSummary active={active} stamp={stamp} />}

      <div className="flex items-center justify-between gap-4">
        <p className="text-muted-foreground text-sm">
          Todas las corridas del mirror, la más nueva primero. Solo se puede
          elegir una con datos cargados (`loaded_data`).
        </p>
        <Button type="button" variant="outline" size="sm" onClick={() => void refresh()}>
          Actualizar
        </Button>
      </div>

      {runs.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No hay corridas en el mirror, o el servicio no respondió.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Corrida</TableHead>
                <TableHead>Ambiente</TableHead>
                <TableHead>Extracción</TableHead>
                <TableHead>Estado extractor</TableHead>
                <TableHead>Carga</TableHead>
                <TableHead>Manifest</TableHead>
                <TableHead className="text-right">Acción</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((run) => {
                const canChoose = run.can_activate && !run.is_active
                const busy = pendingRunId === run.run_id
                return (
                  <TableRow key={`${run.env}:${run.run_id}`}>
                    <TableCell className="font-mono text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        {run.run_id}
                        {run.is_active && <Badge>Vigente</Badge>}
                      </div>
                    </TableCell>
                    <TableCell>{run.env}</TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {formatWhen(run.created_at_utc)}
                      {run.extractor_version ? (
                        <span className="block">{run.extractor_version}</span>
                      ) : null}
                    </TableCell>
                    <TableCell>{run.status ?? "—"}</TableCell>
                    <TableCell>
                      <LoadFlags run={run} />
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {shortHash(run.manifest_sha256)}
                    </TableCell>
                    <TableCell className="text-right">
                      {run.is_active ? (
                        <span className="text-muted-foreground text-xs">En vigor</span>
                      ) : canChoose ? (
                        <Button
                          type="button"
                          size="sm"
                          disabled={busy}
                          aria-busy={busy}
                          onClick={() => void activate(run)}
                        >
                          Activar
                        </Button>
                      ) : (
                        <span className="text-muted-foreground text-xs">
                          {run.can_activate ? "—" : "Sin datos"}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}

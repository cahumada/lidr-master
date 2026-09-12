"use client"

import type * as React from "react"
import { useMemo, useState } from "react"

import { Input } from "@/components/ui/input"
import type { TableDictionaryDetail } from "@/lib/ai-service/types"

/**
 * The full dictionary of one table, fetched when it is opened.
 *
 * It is not in the prompt and it is not meant to be: twelve tables in this
 * shape measured 15,969 tokens against a 16,384-token context ceiling that
 * already spends ~7,000 on evidence. The answer carries the table's
 * description; the 132 columns of CERTIFICAT are read here, when somebody asks.
 *
 * || El diccionario completo de una tabla, pedido al abrirla. No está en el
 * prompt ni debería: 12 tablas así midieron 15.969 tokens.
 */

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; detail: TableDictionaryDetail }
  | { kind: "absent" }
  | { kind: "error"; message: string }

function Mark({ label, title }: { label: string; title: string }) {
  return (
    <span
      title={title}
      className="border-muted-foreground/30 text-muted-foreground rounded border px-1 text-[9px]"
    >
      {label}
    </span>
  )
}

function Detail({ detail }: { detail: TableDictionaryDetail }) {
  const [filter, setFilter] = useState("")
  const columns = detail.columns
  const shown = useMemo(() => {
    if (!columns) return []
    const needle = filter.trim().toUpperCase()
    if (!needle) return columns
    return columns.filter(
      (column) =>
        column.name.toUpperCase().includes(needle) ||
        (column.description ?? "").toUpperCase().includes(needle),
    )
  }, [columns, filter])

  return (
    <div className="flex flex-col gap-3">
      {detail.description_es && (
        <p className="text-[11px] leading-relaxed whitespace-pre-line">
          {detail.description_es}
        </p>
      )}

      <dl className="flex flex-col gap-1 text-[11px]">
        <div className="flex gap-2">
          <dt className="text-muted-foreground w-10 shrink-0">PK</dt>
          <dd className="font-mono">
            {detail.primary_key.length > 0
              ? detail.primary_key.join(", ")
              : "(sin clave primaria declarada)"}
          </dd>
        </div>
        {detail.foreign_keys.length > 0 && (
          <div className="flex gap-2">
            <dt className="text-muted-foreground w-10 shrink-0">FK</dt>
            <dd className="flex flex-col gap-0.5 font-mono">
              {detail.foreign_keys.map((key) => (
                <span key={key.name}>
                  {key.columns.join(", ")} → {key.references_table ?? "?"}
                </span>
              ))}
            </dd>
          </div>
        )}
        {detail.indexes.length > 0 && (
          <div className="flex gap-2">
            <dt className="text-muted-foreground w-10 shrink-0">Índices</dt>
            <dd className="flex flex-col gap-0.5 font-mono">
              {detail.indexes.map((index) => (
                <span key={index.name}>
                  {index.name}
                  {index.unique ? " (único)" : ""}: {index.columns.join(", ")}
                </span>
              ))}
            </dd>
          </div>
        )}
      </dl>

      {/* `null` is not `[]`: the run not extracting columns is a different fact
          from a table having none, and §12 of the domain note says so.
          || `null` no es `[]`: que la corrida no las extrajera es distinto de
          que la tabla no tenga. */}
      {columns === null ? (
        <p className="text-muted-foreground text-[11px]">
          La corrida no extrajo las columnas de esta tabla. No es que no tenga.
        </p>
      ) : columns.length === 0 ? (
        <p className="text-muted-foreground text-[11px]">
          La corrida declara que esta tabla no tiene columnas.
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline gap-2">
            <Input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filtrar columna…"
              className="h-7 text-xs"
            />
            <span className="text-muted-foreground shrink-0 text-[10px]">
              {shown.length} de {columns.length}
            </span>
          </div>
          <ul className="max-h-72 overflow-auto pr-1">
            {shown.map((column) => (
              <li key={column.name} className="border-b py-1 last:border-0">
                <div className="flex flex-wrap items-baseline gap-1.5">
                  <span className="font-mono text-[11px] font-medium">
                    {column.name}
                  </span>
                  {column.is_primary_key && <Mark label="PK" title="Clave primaria" />}
                  {column.is_foreign_key && <Mark label="FK" title="Clave foránea" />}
                  {column.data_type && (
                    <span className="text-muted-foreground text-[10px]">
                      {column.data_type}
                    </span>
                  )}
                  {column.nullable === false && (
                    <span className="text-muted-foreground text-[10px]">NOT NULL</span>
                  )}
                </div>
                {column.description && (
                  <p className="text-muted-foreground text-[10px] leading-snug">
                    {column.description}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function TableDictionary({
  tableName,
  summary,
}: {
  tableName: string
  /** The row the reader clicks: name, role and counts. Passed in so the
   * disclosure wraps the WHOLE row instead of sitting inside a flex line,
   * where the expanded panel would be squeezed into a wrapped column.
   * || La fila que se clickea. Se pasa desde afuera para que el desplegable
   * envuelva la fila ENTERA. */
  summary: React.ReactNode
}) {
  const [state, setState] = useState<State>({ kind: "idle" })

  async function load() {
    if (state.kind === "ready" || state.kind === "loading") return
    setState({ kind: "loading" })
    try {
      const response = await fetch(
        `/api/business-db/tables/${encodeURIComponent(tableName)}`,
      )
      if (response.status === 404) {
        setState({ kind: "absent" })
        return
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        setState({
          kind: "error",
          message: body?.error ?? `El servicio respondió ${response.status}.`,
        })
        return
      }
      setState({ kind: "ready", detail: await response.json() })
    } catch {
      setState({ kind: "error", message: "No se pudo contactar a la consola." })
    }
  }

  return (
    <details
      className="group"
      onToggle={(event) => {
        if ((event.currentTarget as HTMLDetailsElement).open) void load()
      }}
    >
      <summary className="cursor-pointer list-none">{summary}</summary>
      <div className="mt-2 mb-1 rounded-md border p-2">
        {state.kind === "loading" && (
          <p className="text-muted-foreground text-[11px]">Cargando…</p>
        )}
        {state.kind === "absent" && (
          <p className="text-[11px]">
            La corrida activa no tiene esta tabla en su diccionario.
          </p>
        )}
        {state.kind === "error" && (
          <p className="text-destructive text-[11px]">{state.message}</p>
        )}
        {state.kind === "ready" && <Detail detail={state.detail} />}
      </div>
    </details>
  )
}

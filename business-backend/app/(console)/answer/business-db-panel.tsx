"use client"

import type {
  BusinessDbContextView,
  CodeResolution,
  DependencyTable,
  ResolutionOutcome,
} from "@/lib/ai-service/types"

/**
 * Where the answer's database context came from: run, anchored codes, and for
 * each one the chain code → routines → tables.
 *
 * The service has returned `business_db` since `add-business-db-context` and
 * the console dropped it. With a routine-level chain that stops being a missing
 * nicety: a table asserted in an answer with no way to see which routine
 * justifies it is the same defect as a chunk with no document.
 *
 * || De dónde salió el contexto de base de la respuesta. Con la cadena a nivel
 * rutina, no mostrarlo es el mismo defecto que un chunk sin documento.
 */

/** Spanish labels for the closed vocabulary. A cause with no entry is shown
 * verbatim: an unmapped value means the console is behind the service, not that
 * the user did something wrong.
 * || Una causa sin entrada se muestra tal cual: consola desfasada. */
const CAUSE_LABEL: Partial<Record<ResolutionOutcome, string>> = {
  edges_not_built: "la corrida activa no tiene construidas las tablas por dependencia",
  no_dependency_routine: "ninguna rutina de la base nombra este código",
  routine_without_tables: "sus rutinas no dependen de ninguna tabla",
  code_too_short_to_anchor: "el código es demasiado corto para anclar",
  dependency_tables_capped: "toca más tablas que el tope configurado",
  role_unknown: "hay tablas cuyo rol no se pudo derivar de una regla declarada",
  table_not_in_dictionary: "la tabla no está en el diccionario de la corrida",
  table_not_loaded: "la tabla no tiene filas cargadas en esta corrida",
  rows_capped: "la tabla tiene más filas que el tope configurado",
  columns_unknown: "la tabla no tiene columnas extraídas",
  date_unparsed: "hay fechas que no se pudieron interpretar",
  dropped_by_budget: "se recortó para entrar en el presupuesto de tokens",
  not_in_run: "el código no aparece en WINDOWS de esta corrida",
  no_maintained_table: "no declara tabla que mantenga",
  ng_identi_ignored_by_type: "declara NG_IDENTI pero no es tipo 10; se ignora",
  no_validity_mechanism: "no tiene mecanismo de vigencia declarado",
  validity_discrepancy: "hay filas donde estado y período discrepan",
}

const ROLE_LABEL: Record<DependencyTable["role"], string> = {
  reference: "referencia",
  historical: "histórica",
  message: "mensajes",
  validation: "validación",
  unknown: "rol no declarado",
}

const ROLE_CLASS: Record<DependencyTable["role"], string> = {
  reference: "border-sky-500/40 text-sky-700 dark:text-sky-300",
  historical: "border-violet-500/40 text-violet-700 dark:text-violet-300",
  message: "border-teal-500/40 text-teal-700 dark:text-teal-300",
  validation: "border-amber-500/40 text-amber-700 dark:text-amber-300",
  unknown: "border-muted-foreground/30 text-muted-foreground",
}

/** Causes the service counts as incompleteness. Kept as a list so a cause the
 * console does not know still shows up in the notice.
 * || Causas que el servicio cuenta como incompletitud. */
const INCOMPLETE: ResolutionOutcome[] = [
  "table_not_in_dictionary",
  "table_not_loaded",
  "rows_capped",
  "columns_unknown",
  "date_unparsed",
  "dropped_by_budget",
  "edges_not_built",
  "dependency_tables_capped",
]

function causeText(cause: ResolutionOutcome): string {
  return CAUSE_LABEL[cause] ?? cause
}

function TableRow({ table }: { table: DependencyTable }) {
  return (
    <li className="border-l pl-3">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="font-mono text-xs font-medium">{table.table_name}</span>
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] ${ROLE_CLASS[table.role]}`}
          title={table.role_reason}
        >
          {ROLE_LABEL[table.role]}
        </span>
        <span className="text-muted-foreground text-[11px]">
          {table.routine_hits}/{table.routine_total} rutinas
        </span>
      </div>
      {table.description && (
        <p className="text-muted-foreground mt-0.5 text-[11px]">{table.description}</p>
      )}
      <p className="text-muted-foreground mt-0.5 font-mono text-[10px] break-words">
        vía {table.via_routines.join(", ")}
      </p>
    </li>
  )
}

function Resolution({ resolution }: { resolution: CodeResolution }) {
  const hidden = resolution.dependency_tables_total - resolution.dependency_tables.length
  return (
    <div className="space-y-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-mono text-xs font-semibold">{resolution.code}</span>
        {resolution.window_description && (
          <span className="text-muted-foreground text-xs">
            {resolution.window_description}
          </span>
        )}
        {resolution.window_status && (
          <span className="text-muted-foreground text-[11px]">
            · {resolution.window_status}
          </span>
        )}
      </div>

      {resolution.table_name && (
        <p className="text-xs">
          Tabla que mantiene:{" "}
          <span className="font-mono">{resolution.table_name}</span>
        </p>
      )}

      {resolution.dependency_tables.length > 0 ? (
        <>
          <p className="text-muted-foreground text-[11px]">
            Tablas que toca ({resolution.dependency_tables_total}
            {hidden > 0 ? `, se muestran ${resolution.dependency_tables.length}` : ""}).
            El orden es por cuántas rutinas de la transacción llegan a cada una; no
            es una jerarquía de importancia declarada.
          </p>
          <ul className="space-y-2">
            {resolution.dependency_tables.map((table) => (
              <TableRow key={table.table_name} table={table} />
            ))}
          </ul>
        </>
      ) : (
        <p className="text-muted-foreground text-[11px]">
          Sin tablas por dependencia
          {resolution.causes.length > 0 ? `: ${causeText(resolution.causes[0])}` : "."}
        </p>
      )}
    </div>
  )
}

export function BusinessDbPanel({ context }: { context: BusinessDbContextView }) {
  // No block reached the prompt: say nothing rather than render an empty
  // section that reads as "the base had nothing to say".
  // || No llegó bloque al prompt: no se muestra nada.
  if (!context.block_emitted) return null

  const causes = new Set<ResolutionOutcome>()
  for (const resolution of context.resolutions) {
    for (const cause of resolution.causes) {
      if (INCOMPLETE.includes(cause)) causes.add(cause)
    }
  }
  const edgesMissing = causes.has("edges_not_built")

  return (
    <div className="space-y-2">
      {!context.complete && (
        <p className="rounded-lg border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs">
          Contexto de base incompleto:{" "}
          {causes.size > 0
            ? Array.from(causes).map(causeText).join("; ")
            : "quedó algo afuera"}
          .{" "}
          {edgesMissing && (
            <>
              Construí las tablas por dependencia para la corrida activa desde{" "}
              <a href="/business-db" className="underline underline-offset-2">
                Base de datos
              </a>
              .
            </>
          )}
        </p>
      )}
      <details className="rounded-lg border">
        <summary className="text-muted-foreground cursor-pointer px-3 py-2 text-xs font-medium">
          Contexto de base ({context.resolutions.length}{" "}
          {context.resolutions.length === 1 ? "código anclado" : "códigos anclados"})
        </summary>
        <div className="space-y-3 border-t p-3">
          <p className="text-muted-foreground text-[11px]">
            Corrida <span className="font-mono">{context.run_id ?? "—"}</span> ·
            ambiente {context.env ?? "—"}
            {context.as_of ? ` · vigencia al ${context.as_of}` : ""}. Es otra
            autoridad que la especificación funcional: si difieren, es un hallazgo,
            no un error a resolver.
          </p>
          {context.resolutions.map((resolution) => (
            <Resolution key={resolution.code} resolution={resolution} />
          ))}
          {context.dropped_codes.length > 0 && (
            <p className="text-muted-foreground text-[11px]">
              El tope de códigos anclados dejó afuera:{" "}
              {context.dropped_codes.join(", ")}.
            </p>
          )}
        </div>
      </details>
    </div>
  )
}

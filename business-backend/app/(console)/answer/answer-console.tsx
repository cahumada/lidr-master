"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import {
  ArrowUp,
  Check,
  History,
  Loader2,
  PanelLeft,
  PanelLeftClose,
  Pencil,
  Plus,
  RefreshCw,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react"

import { AnswerMarkdown } from "./answer-markdown"
import { BusinessDbPanel } from "./business-db-panel"
import { LiveFlowPanel } from "./live-flow-panel"
import { WindowStatusBadge } from "@/components/window-status-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { useIsMobile } from "@/hooks/use-mobile"
import type {
  AnswerAgenticCompleted,
  AnswerAgenticPaused,
  AnswerAgenticProgress,
  AnswerAgenticStart,
  CitationSnapshot,
  ConversationAnchor,
  GraphActivityEntry,
  HistoryTurn,
  RoutingRecord,
  NamedAgentProfile,
  SearchFacets,
  SessionSummary,
  SessionView,
  TokenUsage,
} from "@/lib/ai-service/types"

/**
 * Session chat over independent agentic runs. Each send is still a new
 * `thread_id` — a thread is ONE graph run. The durable transcript lives on
 * the service (`history`); this screen lists and reopens it via
 * `/answer?session=<id>`. A reload restores that id, not React state.
 * || Chat de sesión sobre corridas agenticas independientes. Cada envío sigue
 * siendo un `thread_id` nuevo. El transcript vive en el servicio; esta
 * pantalla lo lista y lo reabre con `/answer?session=<id>`. Un F5 restaura
 * ese id, no el estado de React.
 */

const POLL_INTERVAL_MS = 1200

const SUGGESTIONS = [
  "¿Qué validaciones aplica CA014 al dar de alta una póliza?",
  "¿Cómo se anula una póliza de vida?",
  "¿Qué ventanas intervienen en el alta de un siniestro?",
]

const TOGGLES = [
  {
    name: "rerank" as const,
    label: "Reranker",
    hint: "Medido: p@10 de 0,140 a 0,171 y hallazgo de 86% a 94%, a 3× la latencia.",
  },
  {
    name: "split" as const,
    label: "Descomponer",
    hint: "Divide una pregunta compuesta — el agente query_planner reusa la misma lógica.",
  },
  {
    name: "lexical" as const,
    label: "Rama léxica",
    hint: "Medido: acierto@1 de 77% a 48%. Apagada por default.",
  },
]

type RetrievalFlags = { rerank: boolean; split: boolean; lexical: boolean }

type CitationView = {
  document_id: string
  document_title?: string | null
  section?: string | null
  bullet_path?: string | null
  content_hash: string
  text?: string
  window_status?: string | null
}

type ChatTurn = {
  id: string
  question: string
  activity: GraphActivityEntry[]
  completed: AnswerAgenticCompleted | null
  paused: AnswerAgenticPaused | null
  error: string | null
  elapsedMs: number | null
  pending: boolean
  /** When the operator sent this question. || Cuándo se mandó esta pregunta. */
  askedAt: number | null
  /** Restored from `history`: no live flow, no invented chunk text. */
  reopened?: boolean
  snapshots?: CitationSnapshot[]
  /** Last completion of a live turn. Absent on a reopened history turn. */
  usage?: TokenUsage
}

function historyToTurns(history: HistoryTurn[]): ChatTurn[] {
  return history.map((item, index) => ({
    id: `history-${item.created_at}-${index}`,
    question: item.question,
    activity: [],
    completed: {
      status: "completed",
      thread_id: "reopened",
      question: item.question,
      answer: item.answer,
      citations: [],
      grounded: item.grounded,
      confidence: null,
      needs_human_review: false,
      review_reasons: [],
      routing_history: [],
      resolved_question: item.resolved_question,
      resolved_referents: [],
      session_memory_used: true,
      anchors_applied: [],
      context_truncated: false,
      dropped_hits: 0,
      answer_truncated: false,
    },
    paused: null,
    error: null,
    elapsedMs: null,
    pending: false,
    askedAt: Date.parse(item.created_at) || null,
    reopened: true,
    snapshots: item.citations,
  }))
}

const RELATIVE_TIME = new Intl.RelativeTimeFormat("es-AR", { numeric: "auto" })

function formatTimeAgo(epochMs: number, now: number): string {
  const deltaSec = Math.round((epochMs - now) / 1000)
  const abs = Math.abs(deltaSec)
  if (abs < 45) return "ahora"
  if (abs < 90) return RELATIVE_TIME.format(Math.sign(deltaSec) || -1, "minute")
  if (abs < 3600) return RELATIVE_TIME.format(Math.round(deltaSec / 60), "minute")
  if (abs < 86400) return RELATIVE_TIME.format(Math.round(deltaSec / 3600), "hour")
  if (abs < 86400 * 30) return RELATIVE_TIME.format(Math.round(deltaSec / 86400), "day")
  return RELATIVE_TIME.format(Math.round(deltaSec / 86400 / 30), "month")
}

function formatAskedAt(epochMs: number): string {
  return new Date(epochMs).toLocaleString("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  })
}

function formatSessionWhen(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })
}

function sessionHref(sessionId: string | null): string {
  return sessionId ? `/answer?session=${encodeURIComponent(sessionId)}` : "/answer"
}

function UserTurnMeta({
  askedAt,
  now,
  canRetry,
  onRetry,
}: {
  askedAt: number | null
  now: number
  canRetry: boolean
  onRetry: () => void
}) {
  return (
    <div className="flex items-center gap-1">
      {askedAt !== null && (
        <time
          className="text-muted-foreground text-[11px]"
          dateTime={new Date(askedAt).toISOString()}
          title={formatAskedAt(askedAt)}
        >
          {formatTimeAgo(askedAt, now)}
        </time>
      )}
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Reintentar esta pregunta"
        title="Reintentar esta pregunta"
        disabled={!canRetry}
        onClick={onRetry}
      >
        <RefreshCw />
      </Button>
    </div>
  )
}

function newTurnId(): string {
  return `turn-${crypto.randomUUID()}`
}

function elapsedSince(startedAt: number): number {
  return Math.round(Date.now() - startedAt)
}

function MultiSelectFilter({
  label,
  allLabel,
  options,
  selected,
  onChange,
}: {
  label: string
  allLabel: string
  options: string[]
  selected: string[]
  onChange: (next: string[]) => void
}) {
  const isAll = selected.length === 0

  function toggle(option: string) {
    onChange(
      selected.includes(option)
        ? selected.filter((value) => value !== option)
        : [...selected, option],
    )
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs">{label}</Label>
      <div className="flex max-h-40 flex-col gap-1.5 overflow-y-auto rounded-lg border p-2.5">
        <label className="flex items-center gap-2 text-sm font-medium">
          <Checkbox checked={isAll} onCheckedChange={() => onChange([])} />
          {allLabel}
        </label>
        {options.length === 0 ? (
          <p className="text-muted-foreground text-xs">Sin valores en el corpus todavía.</p>
        ) : (
          options.map((option) => (
            <label key={option} className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={selected.includes(option)}
                onCheckedChange={() => toggle(option)}
              />
              <span className="truncate">{option}</span>
            </label>
          ))
        )}
      </div>
    </div>
  )
}

function sourceBadgeClass(source: string): string {
  if (source === "llm") return "border-primary/40 bg-primary/10 text-primary"
  if (source === "fallback") return "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
  return "border-destructive/40 bg-destructive/10 text-destructive"
}

function RoutingTrace({ history }: { history: RoutingRecord[] }) {
  if (history.length === 0) return null
  return (
    <details className="rounded-lg border">
      <summary className="text-muted-foreground cursor-pointer px-3 py-2 text-xs font-medium">
        Enrutado del orquestador ({history.length})
      </summary>
      <ol className="flex flex-col gap-2 border-t p-3">
        {history.map((row) => (
          <li key={`${row.step}-${row.next_agent}`} className="flex flex-wrap items-start gap-2 text-sm">
            <span className="text-muted-foreground w-6 shrink-0 font-mono tabular-nums">
              {row.step + 1}.
            </span>
            <span className="w-44 shrink-0 font-mono">{row.next_agent}</span>
            <Badge variant="outline" className={`text-[10px] ${sourceBadgeClass(row.source)}`}>
              {row.source}
            </Badge>
            <span className="text-muted-foreground min-w-0 flex-1">{row.reason}</span>
          </li>
        ))}
      </ol>
    </details>
  )
}

function CitationList({ hits }: { hits: CitationView[] }) {
  if (hits.length === 0) {
    return <p className="text-muted-foreground text-sm">Sin evidencia recuperada en el corpus.</p>
  }
  return (
    <ol className="flex flex-col gap-3">
      {hits.map((hit, index) => (
        <li key={(hit.content_hash || hit.document_id) + String(index)}>
          <Card>
            <CardContent className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary" className="font-mono text-xs">
                  {hit.document_id}
                </Badge>
                {hit.document_title && (
                  <span className="text-sm">{hit.document_title}</span>
                )}
                <WindowStatusBadge windowStatus={hit.window_status} />
                {hit.section && (
                  <span className="text-muted-foreground text-xs">{hit.section}</span>
                )}
              </div>
              {hit.text ? (
                <p className="bg-muted/40 max-h-40 overflow-y-auto rounded-md p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
                  {hit.text}
                </p>
              ) : null}
            </CardContent>
          </Card>
        </li>
      ))}
    </ol>
  )
}

function AwaitingReviewPanel({
  paused,
  note,
  onNoteChange,
  onResume,
  pending,
}: {
  paused: AnswerAgenticPaused
  note: string
  onNoteChange: (value: string) => void
  onResume: (decision: "approve" | "reject") => void
  pending: boolean
}) {
  return (
    <Alert className="border-amber-500/40 bg-amber-500/5">
      <AlertDescription className="flex flex-col gap-4">
        <div>
          <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
            Esta respuesta necesita revisión humana
          </p>
          <ul className="mt-2 space-y-1">
            {paused.review_reasons.map((reason) => (
              <li key={reason} className="flex gap-2 text-sm">
                <span className="text-amber-600 dark:text-amber-400">·</span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
          {paused.confidence !== null && (
            <p className="text-muted-foreground mt-2 text-xs">
              Confianza{" "}
              <strong className="text-foreground">
                {Math.round(paused.confidence * 100)}%
              </strong>
            </p>
          )}
          <p className="text-muted-foreground mt-1 font-mono text-[10px]">
            thread: {paused.thread_id}
          </p>
        </div>

        {paused.answer && (
          <div className="flex flex-col gap-2 rounded-md border p-3">
            {paused.answer_truncated && (
              <p className="text-destructive text-xs">
                Esta respuesta parcial además quedó cortada por el tope de
                tokens de salida del perfil.
              </p>
            )}
            <AnswerMarkdown>{paused.answer}</AnswerMarkdown>
          </div>
        )}

        {paused.business_db && <BusinessDbPanel context={paused.business_db} />}

        <div className="flex flex-col gap-2">
          <Label htmlFor={`review-note-${paused.thread_id}`} className="text-xs">
            Nota para el registro (opcional)
          </Label>
          <Textarea
            id={`review-note-${paused.thread_id}`}
            value={note}
            onChange={(event) => onNoteChange(event.target.value)}
            placeholder="p. ej. revisado con el equipo de negocio"
            rows={2}
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button disabled={pending} onClick={() => onResume("approve")}>
            {pending ? "Enviando…" : "Aprobar"}
          </Button>
          <Button variant="outline" disabled={pending} onClick={() => onResume("reject")}>
            Rechazar
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  )
}

function RetrievalSheet({
  initialFacets,
  limit,
  onLimitChange,
  moduleCodes,
  onModuleCodesChange,
  windowTypes,
  onWindowTypesChange,
  flags,
  onFlagsChange,
  profiles,
  profileId,
  onProfileIdChange,
}: {
  initialFacets: SearchFacets
  limit: string
  onLimitChange: (value: string) => void
  moduleCodes: string[]
  onModuleCodesChange: (value: string[]) => void
  windowTypes: string[]
  onWindowTypesChange: (value: string[]) => void
  flags: RetrievalFlags
  onFlagsChange: (value: RetrievalFlags) => void
  profiles: NamedAgentProfile[]
  profileId: string
  onProfileIdChange: (value: string) => void
}) {
  return (
    <Sheet>
      <SheetTrigger
        render={
          <Button variant="ghost" size="icon" aria-label="Opciones de recuperación" />
        }
      >
        <SlidersHorizontal />
      </SheetTrigger>
      <SheetContent side="right" className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Opciones de recuperación</SheetTitle>
          <SheetDescription>
            Los mismos knobs medidos que la búsqueda. Aplican al próximo turno,
            no reescriben los anteriores.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 px-4 pb-6">
          {profiles.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="answer-profile" className="text-xs">
                Perfil del sintetizador
              </Label>
              <select
                id="answer-profile"
                value={profileId}
                onChange={(event) => onProfileIdChange(event.target.value)}
                className="border-input bg-background h-9 rounded-md border px-3 text-sm"
              >
                <option value="">Default ({profiles.find((p) => p.is_default)?.name ?? "servicio"})</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}
                    {profile.is_default ? " · default" : ""}
                  </option>
                ))}
              </select>
              <p className="text-muted-foreground text-[10px] leading-relaxed">
                Solo esta corrida. Vacío usa el default persistido, no lo cambia.
              </p>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="answer-limit" className="text-xs">
              Chunks al prompt
            </Label>
            <Input
              id="answer-limit"
              type="number"
              min={1}
              max={100}
              value={limit}
              onChange={(event) => onLimitChange(event.target.value)}
            />
          </div>
          <MultiSelectFilter
            label="Módulo"
            allLabel="Todos"
            options={initialFacets.modules}
            selected={moduleCodes}
            onChange={onModuleCodesChange}
          />
          <MultiSelectFilter
            label="Tipo de ventana"
            allLabel="Cualquiera"
            options={initialFacets.window_types}
            selected={windowTypes}
            onChange={onWindowTypesChange}
          />
          {TOGGLES.map((toggle) => (
            <div key={toggle.name} className="flex items-start gap-3 rounded-lg border p-3">
              <Switch
                id={`answer-${toggle.name}`}
                checked={flags[toggle.name]}
                onCheckedChange={(checked) =>
                  onFlagsChange({ ...flags, [toggle.name]: checked })
                }
                className="mt-0.5"
              />
              <div className="flex flex-col gap-1">
                <Label htmlFor={`answer-${toggle.name}`} className="text-sm">
                  {toggle.label}
                </Label>
                <p className="text-muted-foreground text-xs leading-relaxed">{toggle.hint}</p>
              </div>
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}

const TOKEN_NUMBER = new Intl.NumberFormat("es-AR")

function visibleUsage(
  usage?: TokenUsage,
): TokenUsage | undefined {
  if (!usage) return undefined
  // `reported` is the contract. `total_tokens > 0` covers a payload that
  // sent counts but omitted the flag (older service).
  // || `reported` es el contrato. `total_tokens > 0` cubre un payload que
  // mandó cifras pero omitió el flag (servicio viejo).
  if (usage.reported || usage.total_tokens > 0) return usage
  return undefined
}

function turnUsage(turn: ChatTurn): TokenUsage | undefined {
  return (
    visibleUsage(turn.usage) ??
    visibleUsage(turn.completed?.usage) ??
    visibleUsage(turn.paused?.usage)
  )
}

function UsageMeta({ usage }: { usage?: TokenUsage }) {
  const shown = visibleUsage(usage)
  if (!shown) return null
  return (
    <span title="Última completion de este turno">
      {TOKEN_NUMBER.format(shown.input_tokens)} entrada ·{" "}
      {TOKEN_NUMBER.format(shown.output_tokens)} salida ·{" "}
      {TOKEN_NUMBER.format(shown.total_tokens)} tokens
    </span>
  )
}

function AssistantBody({
  turn,
  reviewNote,
  onNoteChange,
  onResume,
}: {
  turn: ChatTurn
  reviewNote: string
  onNoteChange: (value: string) => void
  onResume: (decision: "approve" | "reject") => void
}) {
  if (turn.error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{turn.error}</AlertDescription>
      </Alert>
    )
  }

  if (turn.paused) {
    return (
      <div className="flex flex-col gap-4">
        <UsageMeta usage={turnUsage(turn)} />
        {turn.paused.resolved_question &&
          turn.paused.resolved_question !== turn.paused.question && (
            <p className="rounded-lg border border-sky-500/40 bg-sky-500/5 px-3 py-2 text-xs">
              Se buscó:{" "}
              <span className="font-medium">{turn.paused.resolved_question}</span>
            </p>
          )}
        <AwaitingReviewPanel
          paused={turn.paused}
          note={reviewNote}
          onNoteChange={onNoteChange}
          onResume={onResume}
          pending={turn.pending}
        />
        {turn.paused.citations.length > 0 && (
          <details className="rounded-lg border">
            <summary className="text-muted-foreground cursor-pointer px-3 py-2 text-xs font-medium">
              Evidencia parcial ({turn.paused.citations.length})
            </summary>
            <div className="border-t p-3">
              <CitationList hits={turn.paused.citations} />
            </div>
          </details>
        )}
      </div>
    )
  }

  if (turn.completed) {
    const result = turn.completed
    const citations = turn.reopened ? (turn.snapshots ?? []) : result.citations
    return (
      <div className="flex flex-col gap-4">
        <div className="text-muted-foreground flex flex-wrap items-center gap-3 text-xs">
          <Badge variant={result.grounded ? "secondary" : "destructive"}>
            {result.grounded ? "grounded" : "sin respaldo en hits"}
          </Badge>
          {result.confidence !== null && (
            <span>confianza {Math.round(result.confidence * 100)}%</span>
          )}
          {turn.elapsedMs !== null && <span>{turn.elapsedMs} ms</span>}
          <UsageMeta usage={turnUsage(turn)} />
          {!turn.reopened && (
            <span className="font-mono">{result.thread_id.slice(0, 8)}…</span>
          )}
        </div>
        {result.resolved_question &&
          result.resolved_question !== result.question && (
            <p className="rounded-lg border border-sky-500/40 bg-sky-500/5 px-3 py-2 text-xs">
              Se buscó:{" "}
              <span className="font-medium">{result.resolved_question}</span>
              {result.resolved_referents.length > 0 && (
                <>
                  {" "}
                  — la sesión resolvió la referencia con{" "}
                  {result.resolved_referents.join(", ")}.
                </>
              )}
            </p>
          )}
        {result.context_truncated && (
          <p className="rounded-lg border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs">
            Evidencia recortada: {result.dropped_hits}{" "}
            {result.dropped_hits === 1 ? "chunk recuperado no entró" : "chunks recuperados no entraron"}{" "}
            en el presupuesto de contexto, así que el modelo no los vio. La respuesta se
            apoya solo en la evidencia listada abajo.
          </p>
        )}
        {result.answer_truncated && (
          <p className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs">
            Respuesta incompleta: el modelo llegó al tope de tokens de salida y
            se cortó a mitad. Lo que falta suele incluir el cierre de fuentes.
            Subí el tope de salida del perfil vigente en{" "}
            <a href="/agents" className="underline underline-offset-2">
              Agentes
            </a>
            .
          </p>
        )}
        <AnswerMarkdown>{result.answer}</AnswerMarkdown>
        <details className="rounded-lg border">
          <summary className="text-muted-foreground cursor-pointer px-3 py-2 text-xs font-medium">
            Evidencia recuperada ({citations.length})
          </summary>
          <div className="border-t p-3">
            <CitationList hits={citations} />
          </div>
        </details>
        {result.business_db && <BusinessDbPanel context={result.business_db} />}
        {!turn.reopened && <RoutingTrace history={result.routing_history} />}
      </div>
    )
  }

  if (turn.activity.length > 0 || turn.pending) {
    return <LiveFlowPanel activity={turn.activity} running={turn.pending && !turn.paused} />
  }

  return (
    <p className="text-muted-foreground text-sm">Preparando la corrida…</p>
  )
}

function ThreadList({
  threads,
  loading,
  error,
  activeId,
  renameError,
  editing,
  titleDraft,
  onTitleDraftChange,
  onStartRename,
  onCancelRename,
  onConfirmRename,
  renaming,
  onSelect,
  onAskDelete,
  onCancelDelete,
  onDelete,
  confirmingId,
  deletingId,
  onCollapse,
}: {
  threads: SessionSummary[]
  loading: boolean
  error: string | null
  activeId: string | null
  renameError: string | null
  editing: boolean
  titleDraft: string
  onTitleDraftChange: (value: string) => void
  onStartRename: () => void
  onCancelRename: () => void
  onConfirmRename: () => void
  renaming: boolean
  onSelect: (id: string) => void
  onAskDelete: (id: string) => void
  onCancelDelete: () => void
  onDelete: (id: string) => void
  confirmingId: string | null
  deletingId: string | null
  onCollapse?: () => void
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-start gap-2 px-3 py-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">Conversaciones de este entorno</p>
          <p className="text-muted-foreground mt-0.5 text-[11px] leading-relaxed">
            Todos los operadores ven los mismos hilos. El servicio no aísla por
            usuario.
          </p>
        </div>
        {onCollapse && (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-expanded
            aria-label="Ocultar conversaciones"
            title="Ocultar conversaciones"
            onClick={onCollapse}
          >
            <PanelLeftClose />
          </Button>
        )}
      </div>
      {error && (
        <Alert variant="destructive" className="mx-3 mb-2">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {renameError && (
        <Alert variant="destructive" className="mx-3 mb-2">
          <AlertDescription>{renameError}</AlertDescription>
        </Alert>
      )}
      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-1 px-2 pb-3">
          {loading ? (
            Array.from({ length: 4 }, (_, index) => (
              <Skeleton key={index} className="h-14 w-full" />
            ))
          ) : threads.length === 0 && !error ? (
            <p className="text-muted-foreground px-2 py-6 text-sm leading-relaxed">
              Todavía no hay conversaciones en este entorno. La primera
              pregunta crea un hilo.
            </p>
          ) : (
            threads.map((thread) => {
              const active = thread.session_id === activeId
              const confirming = thread.session_id === confirmingId
              const deleting = thread.session_id === deletingId
              const listBusy = deletingId !== null || renaming
              return (
                <div
                  key={thread.session_id}
                  aria-busy={deleting}
                  className={`flex items-start gap-1 rounded-lg border px-2 py-2 ${
                    active ? "bg-muted/60 border-border" : "border-transparent"
                  } ${deleting ? "opacity-70" : ""}`}
                >
                  {active && editing ? (
                    <form
                      className="flex min-w-0 flex-1 items-center gap-1"
                      aria-busy={renaming}
                      onSubmit={(event) => {
                        event.preventDefault()
                        if (!renaming) onConfirmRename()
                      }}
                    >
                      <Input
                        value={titleDraft}
                        onChange={(event) => onTitleDraftChange(event.target.value)}
                        aria-label="Título de la conversación"
                        className="h-8 text-sm"
                        autoFocus
                        disabled={renaming}
                      />
                      <Button
                        type="submit"
                        variant="ghost"
                        size="icon-sm"
                        aria-label={renaming ? "Guardando título" : "Guardar título"}
                        disabled={renaming}
                      >
                        {renaming ? <Loader2 className="animate-spin" /> : <Check />}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Cancelar"
                        disabled={renaming}
                        onClick={onCancelRename}
                      >
                        <X />
                      </Button>
                    </form>
                  ) : (
                    <button
                      type="button"
                      disabled={listBusy}
                      onClick={() => onSelect(thread.session_id)}
                      className="flex min-w-0 flex-1 flex-col items-start gap-0.5 rounded-md px-1 py-0.5 text-left disabled:pointer-events-none disabled:opacity-50"
                    >
                      <span className="w-full truncate text-sm font-medium">
                        {thread.title?.trim() || "Sin título"}
                      </span>
                      <span className="text-muted-foreground text-[11px]">
                        {formatSessionWhen(thread.updated_at)}
                        {thread.turn_count > 0
                          ? ` · ${thread.turn_count} ${thread.turn_count === 1 ? "turno" : "turnos"}`
                          : ""}
                      </span>
                    </button>
                  )}
                  {active && !editing && !confirming && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Renombrar"
                      disabled={listBusy}
                      onClick={onStartRename}
                    >
                      <Pencil />
                    </Button>
                  )}
                  {deleting ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      disabled
                      aria-label="Borrando conversación"
                    >
                      <Loader2 className="animate-spin" />
                    </Button>
                  ) : confirming ? (
                    <>
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        disabled={listBusy}
                        onClick={() => onDelete(thread.session_id)}
                      >
                        <Trash2 />
                        ¿Borrar?
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Cancelar borrado"
                        disabled={listBusy}
                        onClick={onCancelDelete}
                      >
                        <X />
                      </Button>
                    </>
                  ) : (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Borrar conversación"
                      disabled={listBusy}
                      onClick={() => onAskDelete(thread.session_id)}
                    >
                      <Trash2 />
                    </Button>
                  )}
                </div>
              )
            })
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

export function AnswerConsole({
  initialFacets,
  profiles,
  initialSessionId,
}: {
  initialFacets: SearchFacets
  profiles: NamedAgentProfile[]
  initialSessionId?: string | null
}) {
  const router = useRouter()
  const isMobile = useIsMobile()
  const [question, setQuestion] = useState("")
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [limit, setLimit] = useState("10")
  const [profileId, setProfileId] = useState("")
  const [moduleCodes, setModuleCodes] = useState<string[]>([])
  const [windowTypes, setWindowTypes] = useState<string[]>([])
  const [flags, setFlags] = useState<RetrievalFlags>({ rerank: true, split: true, lexical: false })
  const [reviewNote, setReviewNote] = useState("")
  const [busy, setBusy] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId ?? null)
  const [anchors, setAnchors] = useState<ConversationAnchor[]>([])
  const [threads, setThreads] = useState<SessionSummary[]>([])
  const [listError, setListError] = useState<string | null>(null)
  const [listLoading, setListLoading] = useState(true)
  const [threadError, setThreadError] = useState<string | null>(null)
  const [listOpen, setListOpen] = useState(false)
  const [listCollapsed, setListCollapsed] = useState(false)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState("")
  const [renameError, setRenameError] = useState<string | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const threadViewportRef = useRef<HTMLDivElement | null>(null)
  const startedAtRef = useRef(0)
  const hydratedFromUrl = useRef<string | null>(null)
  useEffect(() => {
    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current)
    }
  }, [])

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const viewport = threadViewportRef.current
    if (!viewport) return
    viewport.scrollTop = viewport.scrollHeight
  }, [turns])

  async function loadThreads() {
    try {
      const response = await fetch("/api/answer/sessions")
      const body = (await response.json()) as SessionSummary[] & { error?: string }
      if (!response.ok) {
        setListError(body.error ?? "No se pudo cargar el historial.")
        setThreads([])
        return
      }
      setThreads(Array.isArray(body) ? body : [])
      setListError(null)
    } catch {
      setListError("No se pudo contactar a la consola.")
      setThreads([])
    } finally {
      setListLoading(false)
    }
  }

  function stopPolling() {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }
  }

  function clearLocalThread() {
    stopPolling()
    setSessionId(null)
    setAnchors([])
    setTurns([])
    setQuestion("")
    setReviewNote("")
    setBusy(false)
    setEditingTitle(false)
    setTitleDraft("")
    setRenameError(null)
  }

  function newChat() {
    hydratedFromUrl.current = null
    setConfirmingDelete(null)
    clearLocalThread()
    setThreadError(null)
    router.replace("/answer")
    setListOpen(false)
  }

  async function openSession(id: string) {
    stopPolling()
    setBusy(true)
    setThreadError(null)
    setRenameError(null)
    setEditingTitle(false)
    try {
      const response = await fetch(`/api/answer/session/${encodeURIComponent(id)}`)
      const body = (await response.json()) as SessionView & { error?: string }
      if (response.status === 404) {
        hydratedFromUrl.current = null
        setThreadError(body.error ?? "Esa conversación ya no está.")
        clearLocalThread()
        router.replace("/answer")
        return
      }
      if (!response.ok) {
        setThreadError(body.error ?? "No se pudo abrir la conversación.")
        return
      }
      hydratedFromUrl.current = body.session_id
      setSessionId(body.session_id)
      setAnchors(body.anchors)
      setTurns(historyToTurns(body.history))
      setQuestion("")
      setReviewNote("")
      router.replace(sessionHref(body.session_id))
      setListOpen(false)
    } catch {
      setThreadError("No se pudo contactar a la consola.")
    } finally {
      setBusy(false)
    }
  }

  async function deleteThread(id: string) {
    if (deletingId) return
    setDeletingId(id)
    setListError(null)
    try {
      const response = await fetch(`/api/answer/session/${encodeURIComponent(id)}`, {
        method: "DELETE",
      })
      if (!response.ok) {
        const body = (await response.json()) as { error?: string }
        setListError(body.error ?? "No se pudo borrar la conversación.")
        return
      }
      setConfirmingDelete(null)
      if (id === sessionId) {
        newChat()
      }
      await loadThreads()
    } catch {
      setListError("No se pudo contactar a la consola.")
    } finally {
      setDeletingId(null)
    }
  }

  async function confirmRename() {
    if (!sessionId || renaming) return
    setRenaming(true)
    setRenameError(null)
    try {
      const response = await fetch(`/api/answer/session/${encodeURIComponent(sessionId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: titleDraft }),
      })
      const body = (await response.json()) as SessionView & { error?: string }
      if (!response.ok) {
        setRenameError(body.error ?? "No se pudo renombrar.")
        return
      }
      setEditingTitle(false)
      setThreads((current) =>
        current.map((thread) =>
          thread.session_id === body.session_id
            ? { ...thread, title: body.title }
            : thread,
        ),
      )
      await loadThreads()
    } catch {
      setRenameError("No se pudo contactar a la consola.")
    } finally {
      setRenaming(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    fetch("/api/answer/sessions", { signal: controller.signal })
      .then(async (response) => {
        const body = (await response.json()) as SessionSummary[] & { error?: string }
        if (controller.signal.aborted) return
        if (!response.ok) {
          setListError(body.error ?? "No se pudo cargar el historial.")
          setThreads([])
          return
        }
        setThreads(Array.isArray(body) ? body : [])
        setListError(null)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof DOMException && error.name === "AbortError") return
        setListError("No se pudo contactar a la consola.")
        setThreads([])
      })
      .finally(() => {
        if (!controller.signal.aborted) setListLoading(false)
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!initialSessionId) return
    if (hydratedFromUrl.current === initialSessionId) return
    hydratedFromUrl.current = initialSessionId
    const controller = new AbortController()
    fetch(`/api/answer/session/${encodeURIComponent(initialSessionId)}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        const body = (await response.json()) as SessionView & { error?: string }
        if (controller.signal.aborted) return
        if (response.status === 404) {
          hydratedFromUrl.current = null
          setThreadError(body.error ?? "Esa conversación ya no está.")
          setSessionId(null)
          setAnchors([])
          setTurns([])
          router.replace("/answer")
          return
        }
        if (!response.ok) {
          setThreadError(body.error ?? "No se pudo abrir la conversación.")
          return
        }
        setSessionId(body.session_id)
        setAnchors(body.anchors)
        setTurns(historyToTurns(body.history))
        setThreadError(null)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof DOMException && error.name === "AbortError") return
        setThreadError("No se pudo contactar a la consola.")
      })
    return () => controller.abort()
  }, [initialSessionId, router])

  function patchTurn(id: string, patch: Partial<ChatTurn>) {
    setTurns((current) =>
      current.map((turn) => (turn.id === id ? { ...turn, ...patch } : turn)),
    )
  }

  function pollProgress(turnId: string, threadId: string, startedAt: number, fallbackQuestion: string) {
    const poll = async () => {
      try {
        const response = await fetch(`/api/answer/agentic/${threadId}/progress`, {
          headers: { Accept: "application/json" },
        })
        const body = (await response.json()) as AnswerAgenticProgress & { error?: string }
        if (!response.ok) {
          patchTurn(turnId, {
            error: body.error ?? "No se pudo consultar el progreso.",
            pending: false,
          })
          setBusy(false)
          return
        }

        patchTurn(turnId, { activity: body.activity })

        if (body.status === "running") {
          pollTimeoutRef.current = setTimeout(poll, POLL_INTERVAL_MS)
          return
        }

        const elapsedMs = elapsedSince(startedAt)
        setBusy(false)

        if (body.status === "completed") {
          // The service is the authority on what is pinned: an anchor can be
          // added by a question the console never parsed.
          // || El servicio es la autoridad sobre qué está fijado: un anchor
          // puede agregarlo una pregunta que la consola nunca parseó.
          setAnchors(body.anchors_applied ?? [])
          patchTurn(turnId, {
            pending: false,
            elapsedMs,
            completed: {
              status: "completed",
              thread_id: body.thread_id,
              question: body.question ?? fallbackQuestion,
              answer: body.answer ?? "",
              citations: body.citations,
              grounded: body.grounded ?? true,
              confidence: body.confidence,
              needs_human_review: body.needs_human_review ?? false,
              review_reasons: body.review_reasons,
              routing_history: body.routing_history,
              resolved_question: body.resolved_question ?? body.question ?? fallbackQuestion,
              resolved_referents: body.resolved_referents ?? [],
              session_memory_used: body.session_memory_used ?? false,
              anchors_applied: body.anchors_applied ?? [],
              context_truncated: body.context_truncated ?? false,
              dropped_hits: body.dropped_hits ?? 0,
              answer_truncated: body.answer_truncated ?? false,
              usage: body.usage,
              business_db: body.business_db ?? null,
            },
            usage: body.usage,
          })
          void loadThreads()
        } else if (body.status === "awaiting_human_review") {
          patchTurn(turnId, {
            pending: false,
            elapsedMs,
            usage: body.usage,
            paused: {
              status: "awaiting_human_review",
              thread_id: body.thread_id,
              question: body.question ?? fallbackQuestion,
              answer: body.answer,
              citations: body.citations,
              review_reasons: body.review_reasons,
              confidence: body.confidence,
              resolved_question: body.resolved_question ?? body.question ?? fallbackQuestion,
              resolved_referents: body.resolved_referents ?? [],
              session_memory_used: body.session_memory_used ?? false,
              anchors_applied: body.anchors_applied ?? [],
              context_truncated: body.context_truncated ?? false,
              dropped_hits: body.dropped_hits ?? 0,
              answer_truncated: body.answer_truncated ?? false,
              usage: body.usage,
              business_db: body.business_db ?? null,
            },
          })
        } else {
          patchTurn(turnId, {
            pending: false,
            elapsedMs,
            error: body.error ?? "La corrida agentica falló.",
          })
        }
      } catch {
        patchTurn(turnId, {
          error: "No se pudo contactar a la consola.",
          pending: false,
        })
        setBusy(false)
      }
    }
    void poll()
  }

  async function ask(text: string) {
    const trimmed = text.trim()
    if (!trimmed || busy) return

    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }

    const turnId = newTurnId()
    setQuestion("")
    setReviewNote("")
    setBusy(true)
    setTurns((current) => [
      ...current,
      {
        id: turnId,
        question: trimmed,
        activity: [],
        completed: null,
        paused: null,
        error: null,
        elapsedMs: null,
        pending: true,
        askedAt: Date.now(),
      },
    ])

    // The session is created lazily, on the first question rather than on
    // page load: opening the screen and closing it should not leave a row
    // behind. If it cannot be created the turn still goes out, with no
    // memory -- degraded, never blocked.
    // || La sesión se crea perezosamente, en la primera pregunta y no al
    // cargar la pantalla: abrir la pantalla y cerrarla no debería dejar una
    // fila. Si no se puede crear, el turno sale igual sin memoria: degradado,
    // nunca bloqueado.
    const activeSession = sessionId ?? (await ensureSession())

    const payload = {
      question: trimmed,
      session_id: activeSession,
      limit: Number(limit) || 10,
      max_per_document: 1,
      module_code: moduleCodes.length > 0 ? moduleCodes : undefined,
      window_type_name: windowTypes.length > 0 ? windowTypes : undefined,
      lexical: flags.lexical,
      split: flags.split,
      rerank: flags.rerank,
      profile_id: profileId || undefined,
    }

    try {
      const response = await fetch("/api/answer/agentic/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      const body = (await response.json()) as AnswerAgenticStart & { error?: string }
      if (!response.ok) {
        patchTurn(turnId, {
          error: body.error ?? "No se pudo iniciar la consulta agentica.",
          pending: false,
        })
        setBusy(false)
        return
      }
      startedAtRef.current = elapsedSince(0)
      pollProgress(turnId, body.thread_id, startedAtRef.current, trimmed)
    } catch {
      patchTurn(turnId, {
        error: "No se pudo contactar a la consola.",
        pending: false,
      })
      setBusy(false)
    }
  }

  async function resume(decision: "approve" | "reject") {
    const pausedTurn = [...turns].reverse().find((turn) => turn.paused)
    if (!pausedTurn?.paused) return
    patchTurn(pausedTurn.id, { pending: true })
    setBusy(true)

    try {
      const startedAt = Date.now()
      const response = await fetch("/api/answer/agentic/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: pausedTurn.paused.thread_id,
          decision,
          note: reviewNote.trim() || null,
        }),
      })
      const body = (await response.json()) as AnswerAgenticCompleted & { error?: string }
      if (!response.ok) {
        patchTurn(pausedTurn.id, {
          error: body.error ?? "No se pudo reanudar la ejecución.",
          pending: false,
        })
        return
      }
      patchTurn(pausedTurn.id, {
        paused: null,
        completed: body,
        usage: body.usage,
        pending: false,
        elapsedMs: elapsedSince(startedAt),
      })
      void loadThreads()
    } catch {
      patchTurn(pausedTurn.id, {
        error: "No se pudo contactar a la consola.",
        pending: false,
      })
    } finally {
      setBusy(false)
    }
  }

  async function ensureSession(): Promise<string | null> {
    try {
      const response = await fetch("/api/answer/session", { method: "POST" })
      if (!response.ok) return null
      const body = (await response.json()) as { session_id?: string }
      if (!body.session_id) return null
      hydratedFromUrl.current = body.session_id
      setSessionId(body.session_id)
      router.replace(sessionHref(body.session_id))
      return body.session_id
    } catch {
      return null
    }
  }

  async function unpinAnchor(anchor: ConversationAnchor) {
    if (!sessionId) return
    try {
      const response = await fetch(
        `/api/answer/session/${encodeURIComponent(sessionId)}/anchors/` +
          `${encodeURIComponent(anchor.kind)}/${encodeURIComponent(anchor.value)}`,
        { method: "DELETE" },
      )
      if (!response.ok) return
      const body = (await response.json()) as { anchors?: ConversationAnchor[] }
      setAnchors(body.anchors ?? [])
    } catch {
      // Leave the chip where it is: a filter that vanishes from the screen
      // while the service still applies it is worse than one that stayed.
      // || Dejar el chip donde está: un filtro que desaparece de la pantalla
      // mientras el servicio lo sigue aplicando es peor que uno que se quedó.
    }
  }

  function onComposerKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      void ask(question)
    }
  }

  const empty = turns.length === 0
  const threadList = (
    <ThreadList
      threads={threads}
      loading={listLoading}
      error={listError}
      activeId={sessionId}
      renameError={renameError}
      editing={editingTitle}
      titleDraft={titleDraft}
      onTitleDraftChange={setTitleDraft}
      onStartRename={() => {
        const active = threads.find((thread) => thread.session_id === sessionId)
        setTitleDraft(active?.title ?? "")
        setEditingTitle(true)
        setRenameError(null)
        setConfirmingDelete(null)
      }}
      onCancelRename={() => {
        setEditingTitle(false)
        setRenameError(null)
      }}
      renaming={renaming}
      onConfirmRename={() => {
        void confirmRename()
      }}
      onSelect={(id) => {
        setConfirmingDelete(null)
        void openSession(id)
      }}
      confirmingId={confirmingDelete}
      deletingId={deletingId}
      onAskDelete={(id) => {
        setEditingTitle(false)
        setConfirmingDelete(id)
      }}
      onCancelDelete={() => {
        setConfirmingDelete(null)
      }}
      onDelete={(id) => {
        void deleteThread(id)
      }}
      onCollapse={isMobile ? undefined : () => setListCollapsed(true)}
    />
  )

  return (
    <div className="flex h-full min-h-0 flex-1 overflow-hidden">
      {!isMobile && (
        <aside
          className={`bg-background flex shrink-0 flex-col overflow-hidden border-r transition-[width] duration-200 ease-in-out ${
            listCollapsed ? "w-12" : "w-72"
          }`}
        >
          {listCollapsed ? (
            <div className="flex justify-center pt-2">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-expanded={false}
                aria-label="Mostrar conversaciones"
                title="Mostrar conversaciones"
                onClick={() => setListCollapsed(false)}
              >
                <PanelLeft />
              </Button>
            </div>
          ) : (
            threadList
          )}
        </aside>
      )}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="flex shrink-0 items-center gap-1 px-4 py-2">
        {isMobile && (
          <Sheet open={listOpen} onOpenChange={setListOpen}>
            <SheetTrigger
              render={
                <Button variant="ghost" size="icon" aria-label="Conversaciones" />
              }
            >
              <History />
            </SheetTrigger>
            <SheetContent side="left" className="p-0">
              <SheetHeader className="sr-only">
                <SheetTitle>Conversaciones de este entorno</SheetTitle>
                <SheetDescription>
                  Listado de hilos que se pueden reabrir.
                </SheetDescription>
              </SheetHeader>
              {threadList}
            </SheetContent>
          </Sheet>
        )}
        <div className="ml-auto">
          <Button
            variant="ghost"
            size="sm"
            onClick={newChat}
            disabled={empty && !sessionId && !threadError && !question}
          >
            <Plus />
            Chat nuevo
          </Button>
        </div>
      </div>

      {threadError && (
        <Alert variant="destructive" className="mx-4 mb-2 shrink-0">
          <AlertDescription>{threadError}</AlertDescription>
        </Alert>
      )}

      <ScrollArea
        className="min-h-0 flex-1 overflow-hidden"
        viewportRef={threadViewportRef}
      >
      {empty ? (
        <div className="flex min-h-full flex-col items-center justify-center px-4">
          <div className="flex w-full max-w-2xl flex-col items-center gap-8">
            <div className="text-center">
              <h1 className="text-2xl font-semibold tracking-tight">
                Preguntá sobre Visual Time
              </h1>
              <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
                El orquestador planifica, recupera evidencia, sintetiza y valida
                citas. Si la confianza es baja, el turno se pausa para revisión
                humana.
              </p>
            </div>
            <div className="grid w-full gap-2 sm:grid-cols-3">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => void ask(suggestion)}
                  className="bg-card text-card-foreground hover:bg-muted/60 rounded-xl border px-3 py-3 text-left text-sm leading-relaxed transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-4">
            {turns.map((turn) => (
              <article key={turn.id} className="flex flex-col gap-4">
                <div className="flex justify-end">
                  <div className="flex max-w-[85%] flex-col items-end gap-1">
                    <div className="bg-primary text-primary-foreground rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap">
                      {turn.question}
                    </div>
                    <UserTurnMeta
                      askedAt={turn.askedAt}
                      now={now}
                      canRetry={!busy && !turn.pending}
                      onRetry={() => void ask(turn.question)}
                    />
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="bg-card max-w-[85%] rounded-2xl border px-4 py-3">
                    <AssistantBody
                      turn={turn}
                      reviewNote={reviewNote}
                      onNoteChange={setReviewNote}
                      onResume={resume}
                    />
                  </div>
                </div>
              </article>
            ))}
          </div>
      )}
      </ScrollArea>

      <div className="bg-background shrink-0 border-t px-4 py-3">
        {anchors.length > 0 && (
          <div className="mx-auto mb-2 flex w-full max-w-3xl flex-wrap items-center gap-2">
            <span className="text-muted-foreground text-xs">
              Filtros fijados para esta conversación:
            </span>
            {anchors.map((anchor) => (
              <Badge
                key={`${anchor.kind}:${anchor.value}`}
                variant="secondary"
                className="gap-1"
                title={`Fijado por: ${anchor.source_question}`}
              >
                {anchor.kind === "module_code" ? "módulo" : "ventana"} {anchor.value}
                <button
                  type="button"
                  onClick={() => void unpinAnchor(anchor)}
                  aria-label={`Quitar ${anchor.value}`}
                  className="hover:text-destructive ml-1"
                >
                  ×
                </button>
              </Badge>
            ))}
          </div>
        )}
        <form
          className="mx-auto flex w-full max-w-3xl items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            void ask(question)
          }}
        >
          <RetrievalSheet
            initialFacets={initialFacets}
            limit={limit}
            onLimitChange={setLimit}
            moduleCodes={moduleCodes}
            onModuleCodesChange={setModuleCodes}
            windowTypes={windowTypes}
            onWindowTypesChange={setWindowTypes}
            flags={flags}
            onFlagsChange={setFlags}
            profiles={profiles}
            profileId={profileId}
            onProfileIdChange={setProfileId}
          />
          <Textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={onComposerKeyDown}
            placeholder="Escribí una pregunta sobre el corpus…"
            className="min-h-12 max-h-40 flex-1 resize-none"
            aria-label="Pregunta"
            rows={1}
          />
          <Button
            type="submit"
            size="icon"
            disabled={busy || !question.trim()}
            aria-label="Enviar"
          >
            <ArrowUp />
          </Button>
        </form>
        <p className="text-muted-foreground mx-auto mt-2 max-w-3xl text-center text-[11px]">
          Enter envía · Shift+Enter hace un salto de línea. Cada turno es una
          corrida nueva del grafo, pero el hilo tiene memoria: el servicio
          recuerda los filtros, las transacciones nombradas y lo que citó la
          respuesta anterior.
        </p>
      </div>
      </div>
    </div>
  )
}

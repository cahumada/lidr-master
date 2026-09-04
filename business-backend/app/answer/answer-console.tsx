"use client"

import { useEffect, useRef, useState } from "react"
import { ArrowUp, Plus, SlidersHorizontal } from "lucide-react"

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
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import type {
  AnswerAgenticCompleted,
  AnswerAgenticPaused,
  AnswerAgenticProgress,
  AnswerAgenticStart,
  GraphActivityEntry,
  RoutingRecord,
  SearchFacets,
  SearchHit,
} from "@/lib/ai-service/types"

/**
 * Session chat over independent agentic runs. Each send is a new
 * `thread_id`; the thread is presentation, not memory on the service.
 * || Chat de sesión sobre corridas agenticas independientes. Cada envío es
 * un `thread_id` nuevo; el hilo es presentación, no memoria del servicio.
 */

const AGENT_FLOW = [
  { key: "query_planner", label: "Planificador de consulta" },
  { key: "evidence_retriever", label: "Recuperación de evidencia" },
  { key: "answer_synthesizer", label: "Síntesis de respuesta" },
  { key: "citation_validator", label: "Validación de citas" },
] as const

const GATE_KEY = "answer_review_gate"
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

type ChatTurn = {
  id: string
  question: string
  activity: GraphActivityEntry[]
  completed: AnswerAgenticCompleted | null
  paused: AnswerAgenticPaused | null
  error: string | null
  elapsedMs: number | null
  pending: boolean
}

function newTurnId(): string {
  return `turn-${crypto.randomUUID()}`
}

function elapsedSince(startedAt: number): number {
  return Math.round(Date.now() - startedAt)
}

function latestMessageByNode(activity: GraphActivityEntry[]): Record<string, string> {
  const messages: Record<string, string> = {}
  for (const entry of activity) {
    if (entry.node === "orchestrator") continue
    messages[entry.node] = entry.message
  }
  return messages
}

function AgentRow({
  label,
  message,
  state,
}: {
  label: string
  message?: string
  state: "idle" | "running" | "done"
}) {
  const dotClass =
    state === "done"
      ? "bg-emerald-500"
      : state === "running"
        ? "bg-primary animate-pulse"
        : "bg-muted-foreground/30"
  return (
    <li className="flex items-start gap-3 rounded-lg border p-2.5">
      <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${dotClass}`} />
      <div className="flex min-w-0 flex-col">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-muted-foreground truncate text-xs">
          {message ?? (state === "running" ? "…" : "esperando")}
        </span>
      </div>
    </li>
  )
}

function LiveFlowPanel({
  activity,
  running,
}: {
  activity: GraphActivityEntry[]
  running: boolean
}) {
  const messages = latestMessageByNode(activity)
  const runningIndex = running ? AGENT_FLOW.findIndex(({ key }) => !messages[key]) : -1
  const allAgentsDone = runningIndex === -1

  return (
    <div className="flex flex-col gap-2">
      <p className="text-muted-foreground flex items-center gap-2 text-xs">
        {running && <span className="bg-primary inline-block h-2 w-2 animate-pulse rounded-full" />}
        El orquestador está trabajando
      </p>
      <ol className="flex flex-col gap-2">
        {AGENT_FLOW.map(({ key, label }, index) => {
          const message = messages[key]
          const state: "idle" | "running" | "done" = message
            ? "done"
            : index === runningIndex
              ? "running"
              : "idle"
          return <AgentRow key={key} label={label} message={message} state={state} />
        })}
        <AgentRow
          label="Gate de revisión"
          message={messages[GATE_KEY]}
          state={
            messages[GATE_KEY]
              ? "done"
              : running && allAgentsDone
                ? "running"
                : "idle"
          }
        />
      </ol>
    </div>
  )
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

function CitationList({ hits }: { hits: SearchHit[] }) {
  if (hits.length === 0) {
    return <p className="text-muted-foreground text-sm">Sin evidencia recuperada en el corpus.</p>
  }
  return (
    <ol className="flex flex-col gap-3">
      {hits.map((hit, index) => (
        <li key={hit.content_hash + index}>
          <Card>
            <CardContent className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary" className="font-mono text-xs">
                  {hit.document_id}
                </Badge>
                {hit.section && (
                  <span className="text-muted-foreground text-xs">{hit.section}</span>
                )}
              </div>
              <p className="bg-muted/40 max-h-40 overflow-y-auto rounded-md p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
                {hit.text}
              </p>
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
          <div className="rounded-md border p-3">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{paused.answer}</p>
          </div>
        )}

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
          <span className="font-mono">{result.thread_id.slice(0, 8)}…</span>
        </div>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
        <details className="rounded-lg border">
          <summary className="text-muted-foreground cursor-pointer px-3 py-2 text-xs font-medium">
            Evidencia recuperada ({result.citations.length})
          </summary>
          <div className="border-t p-3">
            <CitationList hits={result.citations} />
          </div>
        </details>
        <RoutingTrace history={result.routing_history} />
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

export function AnswerConsole({ initialFacets }: { initialFacets: SearchFacets }) {
  const [question, setQuestion] = useState("")
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [limit, setLimit] = useState("10")
  const [moduleCodes, setModuleCodes] = useState<string[]>([])
  const [windowTypes, setWindowTypes] = useState<string[]>([])
  const [flags, setFlags] = useState<RetrievalFlags>({ rerank: true, split: true, lexical: false })
  const [reviewNote, setReviewNote] = useState("")
  const [busy, setBusy] = useState(false)
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const startedAtRef = useRef(0)

  useEffect(() => {
    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current)
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [turns])

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
            },
          })
        } else if (body.status === "awaiting_human_review") {
          patchTurn(turnId, {
            pending: false,
            elapsedMs,
            paused: {
              status: "awaiting_human_review",
              thread_id: body.thread_id,
              question: body.question ?? fallbackQuestion,
              answer: body.answer,
              citations: body.citations,
              review_reasons: body.review_reasons,
              confidence: body.confidence,
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
      },
    ])

    const payload = {
      question: trimmed,
      limit: Number(limit) || 10,
      max_per_document: 1,
      module_code: moduleCodes.length > 0 ? moduleCodes : undefined,
      window_type_name: windowTypes.length > 0 ? windowTypes : undefined,
      lexical: flags.lexical,
      split: flags.split,
      rerank: flags.rerank,
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
        pending: false,
        elapsedMs: elapsedSince(startedAt),
      })
    } catch {
      patchTurn(pausedTurn.id, {
        error: "No se pudo contactar a la consola.",
        pending: false,
      })
    } finally {
      setBusy(false)
    }
  }

  function resetThread() {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }
    setTurns([])
    setQuestion("")
    setReviewNote("")
    setBusy(false)
  }

  function onComposerKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      void ask(question)
    }
  }

  const empty = turns.length === 0

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex items-center justify-end gap-1 px-4 py-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={resetThread}
          disabled={empty && !question}
        >
          <Plus />
          Chat nuevo
        </Button>
      </div>

      {empty ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-4">
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
        <ScrollArea className="min-h-0 flex-1">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-4">
            {turns.map((turn) => (
              <article key={turn.id} className="flex flex-col gap-4">
                <div className="flex justify-end">
                  <div className="bg-primary text-primary-foreground max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap">
                    {turn.question}
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
            <div ref={bottomRef} />
          </div>
        </ScrollArea>
      )}

      <div className="bg-background border-t px-4 py-3">
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
          corrida nueva: el servicio no recuerda el hilo.
        </p>
      </div>
    </div>
  )
}

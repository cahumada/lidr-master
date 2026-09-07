"use client"

import { useEffect, useState } from "react"
import { Check } from "lucide-react"
import { ThinkingOrb, type OrbState } from "thinking-orbs"

import type { GraphActivityEntry } from "@/lib/ai-service/types"
import { cn } from "@/lib/utils"

const AGENT_FLOW = [
  { key: "query_planner", label: "Planificador de consulta" },
  { key: "evidence_retriever", label: "Recuperación de evidencia" },
  { key: "answer_synthesizer", label: "Síntesis de respuesta" },
  { key: "citation_validator", label: "Validación de citas" },
] as const

const GATE_KEY = "answer_review_gate"

const ORB_BY_STEP: Record<string, OrbState> = {
  query_planner: "solving",
  evidence_retriever: "searching",
  answer_synthesizer: "composing",
  citation_validator: "weaving",
  [GATE_KEY]: "listening",
}

const STATUS_BY_STEP: Record<string, string> = {
  query_planner: "Planificando cómo buscar…",
  evidence_retriever: "Buscando evidencia en el corpus…",
  answer_synthesizer: "Escribiendo la respuesta…",
  citation_validator: "Comprobando que las citas cierren…",
  [GATE_KEY]: "Revisando si hace falta un humano…",
}

function latestMessageByNode(activity: GraphActivityEntry[]): Record<string, string> {
  const messages: Record<string, string> = {}
  for (const entry of activity) {
    if (entry.node === "orchestrator") continue
    messages[entry.node] = entry.message
  }
  return messages
}

function usePrefersReducedMotion(): boolean {
  const [reduce, setReduce] = useState(false)

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)")
    const sync = () => setReduce(query.matches)
    query.addEventListener("change", sync)
    queueMicrotask(sync)
    return () => query.removeEventListener("change", sync)
  }, [])

  return reduce
}

function AgentRow({
  label,
  message,
  state,
  orbState,
  isLast,
  reduceMotion,
}: {
  label: string
  message?: string
  state: "idle" | "running" | "done"
  orbState: OrbState
  isLast: boolean
  reduceMotion: boolean
}) {
  const detail =
    message ?? (state === "running" ? "En curso" : state === "done" ? "Listo" : "En espera")

  return (
    <li
      className={cn(
        "relative flex items-start gap-3 rounded-lg px-2 py-2.5 transition-colors",
        "motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-left-1 motion-safe:duration-300",
        state === "running" && "border-primary/30 bg-primary/5 border",
        state === "done" && "border border-transparent",
        state === "idle" && "border border-transparent opacity-55",
      )}
    >
      {!isLast && (
        <span
          aria-hidden
          className={cn(
            "absolute top-9 bottom-0 left-[18px] w-px",
            state === "done" ? "bg-primary/40" : "bg-border",
          )}
        />
      )}
      <span className="relative z-10 mt-0.5 flex size-7 shrink-0 items-center justify-center">
        {state === "done" && (
          <span className="bg-primary/15 text-primary flex size-6 items-center justify-center rounded-full">
            <Check className="size-3.5" />
            <span className="sr-only">Listo</span>
          </span>
        )}
        {state === "running" && (
          <ThinkingOrb
            state={orbState}
            size={20}
            theme="auto"
            paused={reduceMotion}
            aria-hidden
          />
        )}
        {state === "idle" && (
          <span className="bg-muted-foreground/25 size-2.5 rounded-full" />
        )}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-sm font-medium">{label}</span>
        <span
          className={cn(
            "text-muted-foreground truncate text-xs",
            state === "running" && "motion-safe:animate-pulse",
          )}
        >
          {detail}
        </span>
      </div>
    </li>
  )
}

export function LiveFlowPanel({
  activity,
  running,
}: {
  activity: GraphActivityEntry[]
  running: boolean
}) {
  const reduceMotion = usePrefersReducedMotion()
  const messages = latestMessageByNode(activity)
  const runningIndex = running ? AGENT_FLOW.findIndex(({ key }) => !messages[key]) : -1
  const allAgentsDone = runningIndex === -1
  const gateDone = Boolean(messages[GATE_KEY])
  const gateRunning = running && allAgentsDone && !gateDone
  const activeKey = gateRunning
    ? GATE_KEY
    : runningIndex >= 0
      ? AGENT_FLOW[runningIndex].key
      : running
        ? "connecting"
        : null
  const orbState: OrbState = activeKey
    ? (ORB_BY_STEP[activeKey] ?? "connecting")
    : "breathing"
  const statusLine = activeKey
    ? (STATUS_BY_STEP[activeKey] ?? "Conectando los agentes…")
    : "Preparando la corrida…"

  const steps: Array<{
    key: string
    label: string
    message?: string
    state: "idle" | "running" | "done"
    orbState: OrbState
  }> = [
    ...AGENT_FLOW.map(({ key, label }, index) => {
      const message = messages[key]
      const state: "idle" | "running" | "done" = message
        ? "done"
        : index === runningIndex
          ? "running"
          : "idle"
      return { key, label, message, state, orbState: ORB_BY_STEP[key] ?? "working" }
    }),
    {
      key: GATE_KEY,
      label: "Gate de revisión",
      message: messages[GATE_KEY],
      state: gateDone ? "done" : gateRunning ? "running" : "idle",
      orbState: ORB_BY_STEP[GATE_KEY] ?? "listening",
    },
  ]

  return (
    <div
      className="flex min-w-[16rem] flex-col gap-4"
      aria-live="polite"
      aria-busy={running}
    >
      <div className="flex items-center gap-3">
        <ThinkingOrb
          state={orbState}
          size={64}
          theme="auto"
          paused={reduceMotion || !running}
          aria-label={running ? "El orquestador está trabajando" : "Orquestador"}
        />
        <div className="min-w-0">
          <p className="text-sm font-medium tracking-tight">
            El orquestador está trabajando
          </p>
          <p
            className={cn(
              "text-muted-foreground text-xs leading-relaxed",
              running && "motion-safe:animate-pulse",
            )}
          >
            {statusLine}
          </p>
        </div>
      </div>
      <ol className="flex flex-col">
        {steps.map((step, index) => (
          <AgentRow
            key={step.key}
            label={step.label}
            message={step.message}
            state={step.state}
            orbState={step.orbState}
            isLast={index === steps.length - 1}
            reduceMotion={reduceMotion}
          />
        ))}
      </ol>
    </div>
  )
}

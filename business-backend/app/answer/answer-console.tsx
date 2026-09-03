"use client";

import { useEffect, useRef, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type {
  AnswerAgenticCompleted,
  AnswerAgenticPaused,
  AnswerAgenticProgress,
  AnswerAgenticStart,
  GraphActivityEntry,
  RoutingRecord,
  SearchFacets,
  SearchHit,
} from "@/lib/ai-service/types";

/**
 * Fixed dependency order the orchestrator's fallback ladder follows
 * (`app/domain/graph/orchestrator.py`'s `_ORDER`) — used only to decide
 * which row is "next" when no agent has reported yet, not to reorder
 * anything the backend returns.
 * || Orden de dependencia fijo que sigue la escalera de fallback del
 * orquestador — solo para decidir qué fila es "la que sigue" cuando ningún
 * agente reportó todavía.
 */
const AGENT_FLOW = [
  { key: "query_planner", label: "Planificador de consulta" },
  { key: "evidence_retriever", label: "Recuperación de evidencia" },
  { key: "answer_synthesizer", label: "Síntesis de respuesta" },
  { key: "citation_validator", label: "Validación de citas" },
] as const;

const GATE_KEY = "answer_review_gate";

const POLL_INTERVAL_MS = 1200;

function latestMessageByNode(activity: GraphActivityEntry[]): Record<string, string> {
  const messages: Record<string, string> = {};
  for (const entry of activity) {
    if (entry.node === "orchestrator") continue;
    messages[entry.node] = entry.message;
  }
  return messages;
}

function AgentRow({
  label,
  message,
  state,
}: {
  label: string;
  message?: string;
  state: "idle" | "running" | "done";
}) {
  const dotClass =
    state === "done"
      ? "bg-emerald-500"
      : state === "running"
        ? "bg-primary animate-pulse"
        : "bg-muted-foreground/30";
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
  );
}

function LiveFlowPanel({ activity, running }: { activity: GraphActivityEntry[]; running: boolean }) {
  const messages = latestMessageByNode(activity);
  // Index of the first agent with no message yet — the one "running" right
  // now, per the orchestrator's own dependency ladder. -1 means every agent
  // already reported, so the gate is next.
  // || Índice del primer agente sin mensaje todavía — el que está "corriendo"
  // ahora, según la propia escalera de dependencia del orquestador. -1
  // significa que todos los agentes ya reportaron, así que sigue el gate.
  const runningIndex = running ? AGENT_FLOW.findIndex(({ key }) => !messages[key]) : -1;
  const allAgentsDone = runningIndex === -1;

  const rows = AGENT_FLOW.map(({ key, label }, index) => {
    const message = messages[key];
    const state: "idle" | "running" | "done" = message
      ? "done"
      : index === runningIndex
        ? "running"
        : "idle";
    return <AgentRow key={key} label={label} message={message} state={state} />;
  });

  const gateMessage = messages[GATE_KEY];
  const gateState: "idle" | "running" | "done" = gateMessage
    ? "done"
    : running && allAgentsDone
      ? "running"
      : "idle";

  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold tracking-tight">
            Flujo en vivo
            {running && (
              <span className="bg-primary inline-block h-2 w-2 animate-pulse rounded-full" />
            )}
          </h2>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            Cada agente reporta lo que hace según termina — se actualiza sola cada{" "}
            {(POLL_INTERVAL_MS / 1000).toFixed(1)} s.
          </p>
        </div>
        <ol className="flex flex-col gap-2">
          {rows}
          <AgentRow label="Gate de revisión" message={gateMessage} state={gateState} />
        </ol>
      </CardContent>
    </Card>
  );
}

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
];

function MultiSelectFilter({
  label,
  allLabel,
  options,
  selected,
  onChange,
}: {
  label: string;
  allLabel: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const isAll = selected.length === 0;

  function toggle(option: string) {
    onChange(
      selected.includes(option)
        ? selected.filter((value) => value !== option)
        : [...selected, option],
    );
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
  );
}

function sourceBadgeClass(source: string): string {
  if (source === "llm") return "border-primary/40 bg-primary/10 text-primary";
  if (source === "fallback") return "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400";
  return "border-destructive/40 bg-destructive/10 text-destructive";
}

function RoutingTrace({ history }: { history: RoutingRecord[] }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Enrutado del orquestador</h2>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            Quién decidió cada salto:{" "}
            <span className="text-primary font-medium">llm</span> = elección del modelo ·{" "}
            <span className="font-medium text-amber-700 dark:text-amber-400">fallback</span> =
            escalera determinista ·{" "}
            <span className="text-destructive font-medium">limit</span> = tope de pasos.
          </p>
        </div>
        {history.length === 0 ? (
          <p className="text-muted-foreground text-sm">Sin decisiones registradas.</p>
        ) : (
          <ol className="flex flex-col gap-2">
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
        )}
      </CardContent>
    </Card>
  );
}

function CitationList({ hits }: { hits: SearchHit[] }) {
  if (hits.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">Sin evidencia recuperada en el corpus.</p>
    );
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
  );
}

function AwaitingReviewPanel({
  paused,
  note,
  onNoteChange,
  onResume,
  pending,
}: {
  paused: AnswerAgenticPaused;
  note: string;
  onNoteChange: (value: string) => void;
  onResume: (decision: "approve" | "reject") => void;
  pending: boolean;
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
          <Label htmlFor="review-note" className="text-xs">
            Nota para el registro (opcional)
          </Label>
          <Textarea
            id="review-note"
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
          <Button
            variant="outline"
            disabled={pending}
            onClick={() => onResume("reject")}
          >
            Rechazar
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  );
}

function CompletedPanel({
  result,
  elapsedMs,
}: {
  result: AnswerAgenticCompleted;
  elapsedMs: number | null;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="text-muted-foreground flex flex-wrap items-center gap-3 text-xs">
        <Badge variant={result.grounded ? "secondary" : "destructive"}>
          {result.grounded ? "grounded" : "sin respaldo en hits"}
        </Badge>
        {result.confidence !== null && (
          <span>confianza {Math.round(result.confidence * 100)}%</span>
        )}
        {elapsedMs !== null && <span>{elapsedMs} ms</span>}
        <span className="font-mono">{result.thread_id.slice(0, 8)}…</span>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold">Respuesta</h2>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold">Evidencia recuperada ({result.citations.length})</h2>
        <CitationList hits={result.citations} />
      </div>

      <RoutingTrace history={result.routing_history} />
    </div>
  );
}

export function AnswerConsole({ initialFacets }: { initialFacets: SearchFacets }) {
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState("10");
  const [moduleCodes, setModuleCodes] = useState<string[]>([]);
  const [windowTypes, setWindowTypes] = useState<string[]>([]);
  const [flags, setFlags] = useState({ rerank: true, split: true, lexical: false });
  const [completed, setCompleted] = useState<AnswerAgenticCompleted | null>(null);
  const [paused, setPaused] = useState<AnswerAgenticPaused | null>(null);
  const [activity, setActivity] = useState<GraphActivityEntry[]>([]);
  const [reviewNote, setReviewNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
  }, []);

  function pollProgress(threadId: string, startedAt: number, fallbackQuestion: string) {
    const poll = async () => {
      try {
        const response = await fetch(`/api/answer/agentic/${threadId}/progress`, {
          headers: { Accept: "application/json" },
        });
        const body = (await response.json()) as AnswerAgenticProgress & { error?: string };
        if (!response.ok) {
          setError(body.error ?? "No se pudo consultar el progreso.");
          setPending(false);
          return;
        }

        setActivity(body.activity);

        if (body.status === "running") {
          pollTimeoutRef.current = setTimeout(poll, POLL_INTERVAL_MS);
          return;
        }

        setElapsedMs(Math.round(performance.now() - startedAt));
        setPending(false);

        if (body.status === "completed") {
          setCompleted({
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
          });
        } else if (body.status === "awaiting_human_review") {
          setPaused({
            status: "awaiting_human_review",
            thread_id: body.thread_id,
            question: body.question ?? fallbackQuestion,
            answer: body.answer,
            citations: body.citations,
            review_reasons: body.review_reasons,
            confidence: body.confidence,
          });
        } else {
          setError(body.error ?? "La corrida agentica falló.");
        }
      } catch {
        setError("No se pudo contactar a la consola.");
        setPending(false);
      }
    };
    void poll();
  }

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;

    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }

    setPending(true);
    setError(null);
    setCompleted(null);
    setPaused(null);
    setActivity([]);
    setReviewNote("");
    const startedAt = performance.now();
    const trimmedQuestion = question.trim();

    const payload = {
      question: trimmedQuestion,
      limit: Number(limit) || 10,
      max_per_document: 1,
      module_code: moduleCodes.length > 0 ? moduleCodes : undefined,
      window_type_name: windowTypes.length > 0 ? windowTypes : undefined,
      lexical: flags.lexical,
      split: flags.split,
      rerank: flags.rerank,
    };

    try {
      const response = await fetch("/api/answer/agentic/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await response.json()) as AnswerAgenticStart & { error?: string };
      if (!response.ok) {
        setError(body.error ?? "No se pudo iniciar la consulta agentica.");
        setPending(false);
        return;
      }
      pollProgress(body.thread_id, startedAt, trimmedQuestion);
    } catch {
      setError("No se pudo contactar a la consola.");
      setPending(false);
    }
  }

  async function resume(decision: "approve" | "reject") {
    if (!paused) return;
    setPending(true);
    setError(null);
    const startedAt = performance.now();

    try {
      const response = await fetch("/api/answer/agentic/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: paused.thread_id,
          decision,
          note: reviewNote.trim() || null,
        }),
      });
      const body = (await response.json()) as AnswerAgenticCompleted & { error?: string };
      if (!response.ok) {
        setError(body.error ?? "No se pudo reanudar la ejecución.");
        return;
      }
      setPaused(null);
      setCompleted(body);
    } catch {
      setError("No se pudo contactar a la consola.");
    } finally {
      setElapsedMs(Math.round(performance.now() - startedAt));
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={ask} className="flex flex-col gap-4">
        <div className="flex gap-2">
          <Textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="¿Qué validaciones aplica CA014 al dar de alta una póliza?"
            className="min-h-20 text-base"
            aria-label="Pregunta"
          />
          <Button
            type="submit"
            disabled={pending || !question.trim()}
            className="h-auto shrink-0 px-6"
          >
            {pending && !paused ? "Consultando…" : "Preguntar"}
          </Button>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
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
              onChange={(event) => setLimit(event.target.value)}
            />
          </div>
          <MultiSelectFilter
            label="Módulo"
            allLabel="Todos"
            options={initialFacets.modules}
            selected={moduleCodes}
            onChange={setModuleCodes}
          />
          <MultiSelectFilter
            label="Tipo de ventana"
            allLabel="Cualquiera"
            options={initialFacets.window_types}
            selected={windowTypes}
            onChange={setWindowTypes}
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          {TOGGLES.map((toggle) => (
            <div key={toggle.name} className="flex items-start gap-3 rounded-lg border p-3">
              <Switch
                id={`answer-${toggle.name}`}
                checked={flags[toggle.name]}
                onCheckedChange={(checked) =>
                  setFlags((current) => ({ ...current, [toggle.name]: checked }))
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
      </form>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {activity.length > 0 && !completed && (
        <LiveFlowPanel activity={activity} running={pending && !paused} />
      )}

      {paused && (
        <>
          <AwaitingReviewPanel
            paused={paused}
            note={reviewNote}
            onNoteChange={setReviewNote}
            onResume={resume}
            pending={pending}
          />
          {paused.citations.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold">Evidencia parcial</h2>
              <CitationList hits={paused.citations} />
            </div>
          )}
        </>
      )}

      {completed && <CompletedPanel result={completed} elapsedMs={elapsedMs} />}
    </div>
  );
}

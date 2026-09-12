"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import type { AnswerPromptView } from "@/lib/ai-service/types"

/**
 * The complete context that went to the model, for one turn.
 *
 * Fetched when the modal opens and not before: ~60 KB per turn, read almost
 * never. Rendered as preformatted plain text and NOT as markdown — a prompt is
 * audited for what it literally says, and formatting it hides exactly the
 * characters that matter.
 *
 * || El contexto completo que se le mandó al modelo, para un turno. Se pide al
 * abrir. Texto plano preformateado y NO markdown: un prompt se audita por lo
 * que dice literalmente.
 */

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; prompt: AnswerPromptView }
  | { kind: "gone" }
  | { kind: "error"; message: string }

function Block({ label, text }: { label: string; text: string }) {
  return (
    <section className="flex min-h-0 flex-col gap-1">
      <h3 className="text-muted-foreground text-xs font-semibold tracking-tight">
        {label}
        <span className="ml-2 font-normal">{text.length} caracteres</span>
      </h3>
      {/* `whitespace-pre-wrap` and not a markdown renderer: the blank lines and
          the literal asterisks are the thing being audited.
          || No un renderer de markdown: los asteriscos literales son lo que se
          está auditando. */}
      <pre className="bg-muted/40 max-h-[40vh] overflow-auto rounded-md border p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
        {text}
      </pre>
    </section>
  )
}

export function PromptModal({ promptId }: { promptId: string }) {
  const [state, setState] = useState<State>({ kind: "idle" })

  async function load() {
    if (state.kind === "ready" || state.kind === "loading") return
    setState({ kind: "loading" })
    try {
      const response = await fetch(
        `/api/answer/prompts/${encodeURIComponent(promptId)}`,
      )
      if (response.status === 404) {
        setState({ kind: "gone" })
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
      setState({ kind: "ready", prompt: await response.json() })
    } catch {
      setState({ kind: "error", message: "No se pudo contactar a la consola." })
    }
  }

  return (
    <Dialog
      onOpenChange={(open) => {
        if (open) void load()
      }}
    >
      <DialogTrigger
        render={
          <Button
            variant="link"
            size="sm"
            className="text-muted-foreground h-auto p-0 text-xs"
          />
        }
      >
        Ver el contexto enviado al modelo
      </DialogTrigger>
      <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Contexto enviado al modelo</DialogTitle>
          <DialogDescription>
            {state.kind === "ready" ? (
              <>
                {state.prompt.model}
                {state.prompt.profile_id ? ` · perfil ${state.prompt.profile_id}` : ""}
                {" · presupuesto "}
                {state.prompt.context_budget.toLocaleString("es-AR")} tokens ·{" "}
                {state.prompt.agent}
              </>
            ) : (
              "Lo que realmente se le mandó al modelo en este turno."
            )}
          </DialogDescription>
        </DialogHeader>

        {state.kind === "loading" && (
          <p className="text-muted-foreground text-xs">Cargando…</p>
        )}
        {state.kind === "gone" && (
          <p className="text-xs">
            Este prompt ya no está: la ventana de retención lo borró. Se guardan
            por pocos días porque llevan el corpus recuperado entero, la persona
            y los guardrails.
          </p>
        )}
        {state.kind === "error" && (
          <p className="text-destructive text-xs">{state.message}</p>
        )}
        {state.kind === "ready" && (
          <div className="flex min-h-0 flex-col gap-4 overflow-y-auto">
            <Block label="Sistema" text={state.prompt.system_text} />
            <Block label="Usuario" text={state.prompt.user_text} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

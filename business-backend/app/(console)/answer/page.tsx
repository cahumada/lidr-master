import { serviceConfig } from "@/lib/ai-service/config"
import { facets } from "@/lib/ai-service/search"

import { AnswerConsole } from "./answer-console"

export const metadata = {
  title: "Chat · Visual Time RAG",
}

export default async function AnswerPage(props: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const searchParams = await props.searchParams
  const raw = searchParams.session
  const initialSessionId =
    typeof raw === "string" && raw.trim()
      ? raw.trim()
      : Array.isArray(raw) && typeof raw[0] === "string" && raw[0].trim()
        ? raw[0].trim()
        : null

  const [initialFacets, config] = await Promise.all([
    facets().catch(() => ({ modules: [], window_types: [] })),
    serviceConfig().catch(() => null),
  ])
  const synthesizer = config?.agents.find((agent) => agent.key === "answer_synthesizer")

  return (
    <AnswerConsole
      initialFacets={initialFacets}
      profiles={synthesizer?.profiles ?? []}
      initialSessionId={initialSessionId}
    />
  )
}

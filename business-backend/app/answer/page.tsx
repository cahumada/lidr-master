import { serviceConfig } from "@/lib/ai-service/config"
import { facets } from "@/lib/ai-service/search"

import { AnswerConsole } from "./answer-console"

export const metadata = {
  title: "Chat · Visual Time RAG",
}

export default async function AnswerPage() {
  const [initialFacets, config] = await Promise.all([
    facets().catch(() => ({ modules: [], window_types: [] })),
    serviceConfig().catch(() => null),
  ])
  const synthesizer = config?.agents.find((agent) => agent.key === "answer_synthesizer")

  return (
    <AnswerConsole
      initialFacets={initialFacets}
      profiles={synthesizer?.profiles ?? []}
    />
  )
}

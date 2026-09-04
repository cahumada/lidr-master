import { facets } from "@/lib/ai-service/search"

import { AnswerConsole } from "./answer-console"

export const metadata = {
  title: "Chat · Visual Time RAG",
}

export default async function AnswerPage() {
  const initialFacets = await facets().catch(() => ({ modules: [], window_types: [] }))

  return <AnswerConsole initialFacets={initialFacets} />
}

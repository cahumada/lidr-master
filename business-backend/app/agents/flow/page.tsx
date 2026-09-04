import { PageFrame, PageIntro } from "@/components/page-frame"
import { serviceConfig } from "@/lib/ai-service/config"
import type { GraphFlow } from "@/lib/ai-service/types"

import { FlowConsole } from "./flow-console"

export const metadata = {
  title: "Flujo · Visual Time RAG",
}

const EMPTY_FLOW: GraphFlow = { nodes: [], edges: [], ladder: [] }

export default async function FlowPage() {
  const config = await serviceConfig().catch(() => null)

  return (
    <PageFrame>
      <PageIntro title="Flujo de ejecución">
        El mismo grafo que corre <code>POST /answer/agentic</code>, descrito por
        el servicio. Crear un perfil nombrado no agrega un nodo: el flujo se
        mira acá, no se reescribe.
      </PageIntro>
      <FlowConsole flow={config?.flow ?? EMPTY_FLOW} />
    </PageFrame>
  )
}

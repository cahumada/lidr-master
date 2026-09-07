import Link from "next/link"

import { PageFrame, PageIntro } from "@/components/page-frame"
import { serviceConfig } from "@/lib/ai-service/config"
import type { ServiceConfig } from "@/lib/ai-service/types"

import { AgentsConsole } from "./agents-console"

export const metadata = {
  title: "Agentes · Visual Time RAG",
}

export const dynamic = "force-dynamic"

const UNREACHABLE: ServiceConfig = {
  providers: [],
  models: [],
  persona_max_chars: 0,
  agents: [],
  credential_storage_enabled: false,
  wires: {},
  flow: { nodes: [], edges: [], ladder: [] },
}

export default async function AgentsPage() {
  // Degrades to an empty catalog instead of a crash: the screen's job is to
  // say what the graph is, and "no pude hablar con el servicio" is a more
  // useful thing to render than an error page.
  // || Degrada a un catálogo vacío en vez de romper: el trabajo de la pantalla
  // es decir qué es el grafo, y "no pude hablar con el servicio" es más útil
  // que una página de error.
  const config = await serviceConfig().catch(() => UNREACHABLE)

  return (
    <PageFrame>
      <PageIntro title="Agentes">
        Elegí un agente para ver qué hace. El que llama a un modelo se
        configura con perfiles: voz, reglas extra y modelo. El recorrido del
        grafo está en{" "}
        <Link href="/agents/flow" className="text-foreground underline-offset-4 hover:underline">
          Flujo
        </Link>
        ; los proveedores, en{" "}
        <Link href="/models" className="text-foreground underline-offset-4 hover:underline">
          Modelos
        </Link>
        .
      </PageIntro>
      <AgentsConsole initialConfig={config} />
    </PageFrame>
  )
}

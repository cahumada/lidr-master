import Link from "next/link"

import { PageFrame, PageIntro } from "@/components/page-frame"
import { serviceConfig } from "@/lib/ai-service/config"
import type { ServiceConfig } from "@/lib/ai-service/types"

import { AgentsConsole } from "./agents-console"

export const metadata = {
  title: "Agentes · Visual Time RAG",
}

const UNREACHABLE: ServiceConfig = {
  providers: [],
  models: [],
  persona_max_chars: 0,
  agents: [],
  credential_storage_enabled: false,
  wires: {},
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
      <PageIntro title="Tipos de agentes">
        El catálogo lo sirve el propio servicio IA (<code>GET /config</code>), no
        una copia escrita acá: el rol, las herramientas permitidas y el modelo
        vigente de cada agente salen del grafo que los corre. Los proveedores y
        el catálogo de modelos viven en{" "}
        <Link href="/models" className="text-foreground underline-offset-4 hover:underline">
          Configuración → Modelos
        </Link>
        .
      </PageIntro>
      <AgentsConsole initialConfig={config} />
    </PageFrame>
  )
}

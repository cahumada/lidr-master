import { serviceConfig } from "@/lib/ai-service/config";
import type { ServiceConfig } from "@/lib/ai-service/types";

import { AgentsConsole } from "./agents-console";

export const metadata = {
  title: "Agentes · Visual Time RAG",
};

const UNREACHABLE: ServiceConfig = {
  providers: [],
  models: [],
  persona_max_chars: 0,
  agents: [],
};

export default async function AgentsPage() {
  // Degrades to an empty catalog instead of a crash: the screen's job is to
  // say what the graph is, and "no pude hablar con el servicio" is a more
  // useful thing to render than an error page.
  // || Degrada a un catálogo vacío en vez de romper: el trabajo de la pantalla
  // es decir qué es el grafo, y "no pude hablar con el servicio" es más útil
  // que una página de error.
  const config = await serviceConfig().catch(() => UNREACHABLE);

  return (
    <div className="flex flex-col gap-6">
      <div className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">Agentes</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          El catálogo lo sirve el propio servicio IA (<code>GET /config</code>), no una
          copia escrita acá: el rol, las herramientas permitidas y el modelo vigente de
          cada agente salen del grafo que los corre. Para los agentes que llaman a un
          modelo se puede editar la persona y elegir el modelo entre{" "}
          <strong>OpenAI, Anthropic y Moonshot (Kimi)</strong>.
        </p>
      </div>
      <AgentsConsole initialConfig={config} />
    </div>
  );
}

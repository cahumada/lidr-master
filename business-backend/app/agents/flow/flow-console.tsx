"use client";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { GraphFlow, GraphFlowNode } from "@/lib/ai-service/types";

const KIND_LABEL: Record<string, string> = {
  supervisor: "orquestador",
  agent: "agente",
  gate: "gate",
};

function NodeCard({ node }: { node: GraphFlowNode }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold">{node.label}</h2>
          <Badge variant="outline" className="text-[10px]">
            {KIND_LABEL[node.kind] ?? node.kind}
          </Badge>
          {node.llm_driven && <Badge className="text-[10px]">llama a un modelo</Badge>}
          <code className="text-muted-foreground text-[10px]">{node.key}</code>
        </div>
        <p className="text-sm">{node.role}</p>
        <p className="text-muted-foreground text-xs leading-relaxed">{node.explanation}</p>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">Herramientas:</span>
          {node.tools.length === 0 ? (
            <Badge variant="secondary" className="text-[10px]">
              ninguna
            </Badge>
          ) : (
            node.tools.map((tool) => (
              <Badge key={tool} variant="secondary" className="font-mono text-[10px]">
                {tool}
              </Badge>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function FlowConsole({ flow }: { flow: GraphFlow }) {
  if (flow.nodes.length === 0) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          No se pudo leer el flujo del servicio IA. Esta pantalla no inventa
          nodos: el grafo vive ahí, no acá.
        </AlertDescription>
      </Alert>
    );
  }

  const byKey = Object.fromEntries(flow.nodes.map((node) => [node.key, node]));

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Diagrama</h2>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            Aristas que declara <code>GET /config</code>, no un array escrito en
            esta app. No se editan: cambiar el orden es un change de
            orquestación.
          </p>
        </div>
        <div className="flex flex-col gap-1 font-mono text-xs">
          {flow.edges.map((edge) => (
            <div
              key={`${edge.source}->${edge.target}`}
              className="bg-muted/40 flex flex-wrap items-center gap-2 rounded-md px-3 py-2"
            >
              <span>{byKey[edge.source]?.label ?? edge.source}</span>
              <span className="text-muted-foreground">→</span>
              <span>{byKey[edge.target]?.label ?? edge.target}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Escalera de fallback</h2>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            El orden que usa el orquestador cuando el destino propuesto no es
            legal. Sale de <code>flow.ladder</code>.
          </p>
        </div>
        <ol className="flex flex-col gap-1 text-sm">
          {flow.ladder.map((key, index) => (
            <li key={key} className="flex items-center gap-2">
              <span className="text-muted-foreground w-5 text-xs">{index + 1}.</span>
              <span>{byKey[key]?.label ?? key}</span>
              <code className="text-muted-foreground text-[10px]">{key}</code>
            </li>
          ))}
        </ol>
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Nodos</h2>
        </div>
        {flow.nodes.map((node) => (
          <NodeCard key={node.key} node={node} />
        ))}
      </section>
    </div>
  );
}

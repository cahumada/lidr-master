"use client";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type {
  GraphFlow,
  GraphFlowNode,
  FlowNodeExample,
} from "@/lib/ai-service/types";

const KIND_LABEL: Record<string, string> = {
  supervisor: "orquestador",
  agent: "agente",
  gate: "gate",
};

/**
 * Renders the `backticks` the service writes as code. The catalog's prose is
 * full of them (`decompose()`, `Command(goto=...)`) and showing them raw was
 * half of why the screen read as noise.
 * || Rendea los `backticks` que escribe el servicio como código. La prosa del
 * catálogo está llena de ellos y mostrarlos crudos era la mitad del ruido.
 */
function Prose({ text, className }: { text: string; className?: string }) {
  const parts = text.split(/`([^`]+)`/g);
  return (
    <p className={className}>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <code
            key={index}
            className="bg-muted rounded px-[0.25em] py-0.5 font-mono text-[0.9em]"
          >
            {part}
          </code>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </p>
  );
}

type HubShape = {
  hub: GraphFlowNode;
  spokes: GraphFlowNode[];
  terminal: GraphFlowNode;
  hasStart: boolean;
  hasEnd: boolean;
};

/**
 * The hub the served edges describe, or null when they describe something
 * else. Derived and never assumed: drawing a hub the service did not declare
 * would be the same lie as writing the graph in TypeScript. Every edge has to
 * be accounted for — a picture that silently drops one is worse than a list.
 * || El hub que describen las aristas servidas, o null si describen otra cosa.
 * Derivado, nunca supuesto. Toda arista tiene que quedar dibujada: una imagen
 * que se come una en silencio es peor que una lista.
 */
function hubShape(flow: GraphFlow): HubShape | null {
  const byKey = new Map(flow.nodes.map((node) => [node.key, node]));
  const supervisors = flow.nodes.filter((node) => node.kind === "supervisor");
  if (supervisors.length !== 1) return null;
  const hub = supervisors[0];

  const outgoing = flow.edges.filter((edge) => edge.source === hub.key);
  const returning = new Set(
    flow.edges.filter((edge) => edge.target === hub.key).map((edge) => edge.source),
  );

  const spokes: GraphFlowNode[] = [];
  const terminals: GraphFlowNode[] = [];
  for (const edge of outgoing) {
    const node = byKey.get(edge.target);
    if (!node) return null;
    (returning.has(edge.target) ? spokes : terminals).push(node);
  }
  if (spokes.length === 0 || terminals.length !== 1) return null;
  const terminal = terminals[0];

  const hasStart = flow.edges.some(
    (edge) => edge.source === "START" && edge.target === hub.key,
  );
  const hasEnd = flow.edges.some(
    (edge) => edge.source === terminal.key && edge.target === "END",
  );

  const drawn = new Set<string>();
  for (const spoke of spokes) {
    drawn.add(`${hub.key}->${spoke.key}`);
    drawn.add(`${spoke.key}->${hub.key}`);
  }
  drawn.add(`${hub.key}->${terminal.key}`);
  if (hasStart) drawn.add(`START->${hub.key}`);
  if (hasEnd) drawn.add(`${terminal.key}->END`);
  const everyEdgeDrawn = flow.edges.every((edge) =>
    drawn.has(`${edge.source}->${edge.target}`),
  );
  if (!everyEdgeDrawn) return null;

  return { hub, spokes, terminal, hasStart, hasEnd };
}

/**
 * Execution order: the supervisor, then the ladder it falls back on, then the
 * terminal. `ladder` is served, not written here. Anything the service adds
 * and this order does not name still gets a card, at the end.
 * || Orden de ejecución: el supervisor, después la escalera, después el
 * terminal. `ladder` viene servido. Lo que no entre igual sale, al final.
 */
function walkthroughOrder(flow: GraphFlow): GraphFlowNode[] {
  const byKey = new Map(flow.nodes.map((node) => [node.key, node]));
  const shape = hubShape(flow);
  const ordered: GraphFlowNode[] = [];
  const push = (node: GraphFlowNode | undefined) => {
    if (node && !ordered.includes(node)) ordered.push(node);
  };

  if (shape) push(shape.hub);
  for (const key of flow.ladder) push(byKey.get(key));
  if (shape) push(shape.terminal);
  for (const node of flow.nodes) push(node);
  return ordered;
}

function NodeChip({
  node,
  emphasis = false,
}: {
  node: GraphFlowNode;
  emphasis?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-3 py-1.5 text-xs font-medium ${
        emphasis ? "bg-primary text-primary-foreground border-transparent" : "bg-card"
      }`}
    >
      {node.label}
    </span>
  );
}

function TerminalChip({ label }: { label: string }) {
  return (
    <span className="text-muted-foreground bg-muted inline-flex items-center rounded-full px-3 py-0.5 font-mono text-[10px]">
      {label}
    </span>
  );
}

function HubDiagram({ shape }: { shape: HubShape }) {
  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-fit flex-col items-start gap-1">
        {shape.hasStart && (
          <>
            <TerminalChip label="START" />
            <span className="text-muted-foreground ml-4 text-xs leading-none">↓</span>
          </>
        )}
        <div className="flex items-center gap-3">
          <NodeChip node={shape.hub} emphasis />
          <div className="flex flex-col gap-1">
            {shape.spokes.map((spoke) => (
              <div key={spoke.key} className="flex items-center gap-2">
                <span className="text-muted-foreground font-mono text-xs">⇄</span>
                <NodeChip node={spoke} />
              </div>
            ))}
          </div>
        </div>
        <span className="text-muted-foreground ml-4 text-xs leading-none">↓</span>
        <NodeChip node={shape.terminal} />
        {shape.hasEnd && (
          <>
            <span className="text-muted-foreground ml-4 text-xs leading-none">↓</span>
            <TerminalChip label="END" />
          </>
        )}
      </div>
    </div>
  );
}

function EdgeList({ flow }: { flow: GraphFlow }) {
  const byKey = new Map(flow.nodes.map((node) => [node.key, node]));
  return (
    <div className="flex flex-col gap-1 font-mono text-xs">
      {flow.edges.map((edge) => (
        <div
          key={`${edge.source}->${edge.target}`}
          className="bg-muted/40 flex flex-wrap items-center gap-2 rounded-md px-3 py-2"
        >
          <span>{byKey.get(edge.source)?.label ?? edge.source}</span>
          <span className="text-muted-foreground">→</span>
          <span>{byKey.get(edge.target)?.label ?? edge.target}</span>
        </div>
      ))}
    </div>
  );
}

function ExampleBlock({ example }: { example: FlowNodeExample }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="bg-muted/40 rounded-md px-3 py-2">
          <p className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
            Entra
          </p>
          <Prose className="mt-1 text-xs leading-relaxed" text={example.receives} />
        </div>
        <div className="bg-muted/40 rounded-md px-3 py-2">
          <p className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
            Deja en el estado
          </p>
          <Prose className="mt-1 text-xs leading-relaxed" text={example.leaves} />
        </div>
      </div>
      {example.detail.length > 0 && (
        <ul className="flex flex-col gap-1">
          {example.detail.map((line) => (
            <li
              key={line}
              className="border-muted-foreground/30 text-muted-foreground border-l-2 py-0.5 pl-3 font-mono text-[11px] leading-relaxed"
            >
              {line}
            </li>
          ))}
        </ul>
      )}
      {example.caveat && (
        <div className="flex flex-wrap items-baseline gap-2">
          <Badge variant="outline" className="text-[10px]">
            ilustrativo
          </Badge>
          <Prose
            className="text-muted-foreground flex-1 text-[11px] leading-relaxed"
            text={example.caveat}
          />
        </div>
      )}
    </div>
  );
}

function NodeCard({ node, step }: { node: GraphFlowNode; step: number }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="bg-muted text-muted-foreground flex size-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px]">
            {step}
          </span>
          <h3 className="text-sm font-semibold">{node.label}</h3>
          <Badge variant="outline" className="text-[10px]">
            {KIND_LABEL[node.kind] ?? node.kind}
          </Badge>
          {node.llm_driven && <Badge className="text-[10px]">llama a un modelo</Badge>}
          <code className="text-muted-foreground text-[10px]">{node.key}</code>
        </div>
        <div>
          <p className="text-sm">{node.role}</p>
          <Prose
            className="text-muted-foreground mt-1 text-xs leading-relaxed"
            text={node.explanation}
          />
        </div>
        {node.example && <ExampleBlock example={node.example} />}
        <div className="flex flex-col gap-1 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground">Disponibles:</span>
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
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground">Utilizadas:</span>
            {(node.tools_used ?? []).length === 0 ? (
              <Badge variant="secondary" className="text-[10px]">
                ninguna
              </Badge>
            ) : (
              (node.tools_used ?? []).map((tool) => (
                <Badge key={tool} variant="secondary" className="font-mono text-[10px]">
                  {tool}
                </Badge>
              ))
            )}
          </div>
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

  const shape = hubShape(flow);
  const ordered = walkthroughOrder(flow);
  const byKey = new Map(flow.nodes.map((node) => [node.key, node]));

  return (
    <div className="flex flex-col gap-8">
      {flow.example && (
        <section className="flex flex-col gap-3">
          <div>
            <h2 className="text-sm font-semibold tracking-tight">
              La pregunta que recorre el grafo
            </h2>
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
              {flow.example.note}
            </p>
          </div>
          <Card>
            <CardContent className="flex flex-col gap-2">
              <p className="text-sm leading-relaxed italic">
                «{flow.example.question}»
              </p>
              <code className="text-muted-foreground text-[10px]">
                {flow.example.source}
              </code>
            </CardContent>
          </Card>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Diagrama</h2>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            {shape
              ? "Aristas que declara GET /config, no un array escrito en esta app. El orquestador vuelve a decidir después de cada especialista: por eso las flechas van y vuelven. No se editan: cambiar el orden es un change de orquestación."
              : "Aristas que declara GET /config, no un array escrito en esta app. No tienen forma de hub, así que se listan tal como vienen."}
          </p>
        </div>
        {shape ? <HubDiagram shape={shape} /> : <EdgeList flow={flow} />}
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">
            Los nodos, en orden de ejecución
          </h2>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            Qué hace cada uno, y qué recibe y qué deja cuando la pregunta de
            arriba pasa por él. El ejemplo lo sirve el servicio junto con el
            grafo; lo que depende del modelo o del corpus está marcado como
            ilustrativo.
          </p>
        </div>
        {ordered.map((node, index) => (
          <NodeCard key={node.key} node={node} step={index + 1} />
        ))}
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
              <span>{byKey.get(key)?.label ?? key}</span>
              <code className="text-muted-foreground text-[10px]">{key}</code>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

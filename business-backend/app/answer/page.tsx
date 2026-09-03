import { facets } from "@/lib/ai-service/search";

import { AnswerConsole } from "./answer-console";

export const metadata = {
  title: "Respuesta agentica · Visual Time RAG",
};

export default async function AnswerPage() {
  const initialFacets = await facets().catch(() => ({ modules: [], window_types: [] }));

  return (
    <div className="flex flex-col gap-6">
      <div className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">Respuesta agentica</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          Orquestador con agentes especializados: planificar la consulta, recuperar
          evidencia, sintetizar la respuesta y validar citas. Si la confianza es baja o
          faltan referencias, el grafo pausa para revisión humana — igual que la bandeja
          del supervisor en el curso.
        </p>
      </div>
      <AnswerConsole initialFacets={initialFacets} />
    </div>
  );
}

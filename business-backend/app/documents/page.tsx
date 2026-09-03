import { IngestConsole } from "./ingest-console";

export const metadata = {
  title: "Ingesta · Visual Time RAG",
};

export default function DocumentsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">
          Vista previa de ingesta
        </h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          Subí un documento funcional y mirá cómo queda troceado: una fila por
          fila de tabla, un chunk por bullet narrativo. <strong>No persiste
          nada</strong> — el corpus se construye desde la pantalla de Corpus,
          con el pipeline completo.
        </p>
      </div>
      <IngestConsole />
    </div>
  );
}

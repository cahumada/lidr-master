import { PageFrame, PageIntro } from "@/components/page-frame";
import { IngestConsole } from "./ingest-console";

export const metadata = {
  title: "Ingesta · Visual Time RAG",
};

export default function DocumentsPage() {
  return (
    <PageFrame>
      <PageIntro title="Vista previa de ingesta">
        Subí un documento funcional y mirá cómo queda troceado: una fila por
        fila de tabla, un chunk por bullet narrativo. <strong>No persiste
        nada</strong> — el corpus se construye desde la pantalla de Corpus,
        con el pipeline completo.
      </PageIntro>
      <IngestConsole />
    </PageFrame>
  );
}

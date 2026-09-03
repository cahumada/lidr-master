import { SearchConsole } from "./search-console";

export const metadata = {
  title: "Búsqueda · Visual Time RAG",
};

export default function SearchPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">Búsqueda</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          Recuperación híbrida sobre el corpus indexado. Cada resultado llega
          con su procedencia —documento, sección y qué rama lo encontró— porque
          estas son reglas de negocio de seguros: una respuesta que no se puede
          verificar contra su documento no sirve.
        </p>
      </div>
      <SearchConsole />
    </div>
  );
}

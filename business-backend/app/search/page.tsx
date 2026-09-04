import { PageFrame, PageIntro } from "@/components/page-frame";
import { facets } from "@/lib/ai-service/search";

import { SearchConsole } from "./search-console";

export const metadata = {
  title: "Búsqueda · Visual Time RAG",
};

export default async function SearchPage() {
  // Fetched here, server-side, so the first paint already has the real
  // options instead of a loading list -- and so a facets failure degrades to
  // an empty list of choices instead of taking the whole page down with it.
  // || Se busca acá, del lado del servidor, para que el primer pintado ya
  // tenga las opciones reales en vez de un listado cargando -- y para que una
  // falla de facets degrade a un listado de opciones vacío en vez de tirar
  // abajo la pantalla entera.
  const initialFacets = await facets().catch(() => ({ modules: [], window_types: [] }));

  return (
    <PageFrame>
      <PageIntro title="Búsqueda">
        Recuperación híbrida sobre el corpus indexado. Cada resultado llega
        con su procedencia —documento, sección y qué rama lo encontró— porque
        estas son reglas de negocio de seguros: una respuesta que no se puede
        verificar contra su documento no sirve.
      </PageIntro>
      <SearchConsole initialFacets={initialFacets} />
    </PageFrame>
  );
}

import { toErrorPayload } from "@/lib/ai-service/base-client";
import { corpusIdentity, jobs as recentJobs } from "@/lib/ai-service/corpus";
import type { CorpusIdentity, IngestionJob } from "@/lib/ai-service/types";

import { CorpusConsole } from "./corpus-console";

export const metadata = {
  title: "Corpus · Visual Time RAG",
};

/**
 * The first read happens on the server so the screen arrives with the corpus
 * identity already in it -- the `reset` guard has nothing to check against
 * until that value exists.
 *
 * || La primera lectura pasa en el servidor para que la pantalla llegue con la
 * identidad del corpus adentro -- el guard de `reset` no tiene contra qué
 * chequear hasta que ese valor exista.
 */
export default async function CorpusPage() {
  let identity: CorpusIdentity | null = null;
  let initialJobs: IngestionJob[] = [];
  let identityError: string | null = null;

  try {
    [identity, initialJobs] = await Promise.all([
      corpusIdentity(),
      recentJobs(20),
    ]);
  } catch (error) {
    identityError = toErrorPayload(error).error;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">Corpus</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          Trocear, embeber y cargar, sin una terminal. El trabajo corre en
          segundo plano —trocear son segundos, embeber puede ser horas si cambió
          el texto— así que lo que se ve acá es su estado, no su espera.
        </p>
      </div>
      <CorpusConsole
        identity={identity}
        initialJobs={initialJobs}
        identityError={identityError}
      />
    </div>
  );
}

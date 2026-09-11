import { auth } from "@/auth"
import { PageFrame, PageIntro } from "@/components/page-frame"
import { toErrorPayload } from "@/lib/ai-service/base-client"
import { listRuns } from "@/lib/ai-service/business-db"
import type { ExtractionRunList } from "@/lib/ai-service/types"

import { BusinessDbConsole } from "./business-db-console"

export const metadata = {
  title: "Corridas · Visual Time RAG",
}

export const dynamic = "force-dynamic"

/**
 * First read on the server so the table arrives with real rows. A missing or
 * unreachable endpoint degrades to null + the BFF error — not an error page.
 * || Primera lectura en el servidor para que la tabla llegue con filas reales.
 */
export default async function BusinessDbPage() {
  const session = await auth()
  const declaredBy =
    session?.user?.email?.trim() || session?.user?.name?.trim() || null

  let initial: ExtractionRunList | null = null
  let error: string | null = null

  try {
    initial = await listRuns()
  } catch (cause) {
    error = toErrorPayload(cause).error
  }

  return (
    <PageFrame>
      <PageIntro title="Corridas del mirror">
        Con qué extracción de VisualTIME trabaja el servicio: árbol de
        navegación, estado de ventana y bloque de base. Se listan todas las
        corridas; solo se puede activar una con datos cargados. El estado del
        extractor puede ser parcial — lo que importa es la bandera de datos.
      </PageIntro>
      <BusinessDbConsole
        initial={initial}
        loadError={error}
        declaredBy={declaredBy}
      />
    </PageFrame>
  )
}

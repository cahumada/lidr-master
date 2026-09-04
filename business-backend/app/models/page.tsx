import { PageFrame, PageIntro } from "@/components/page-frame"
import { serviceConfig } from "@/lib/ai-service/config"
import type { ServiceConfig } from "@/lib/ai-service/types"

import { ModelsConsole } from "./models-console"

export const metadata = {
  title: "Modelos · Visual Time RAG",
}

const UNREACHABLE: ServiceConfig = {
  providers: [],
  models: [],
  persona_max_chars: 0,
  agents: [],
  credential_storage_enabled: false,
  wires: {},
}

export default async function ModelsPage() {
  const config = await serviceConfig().catch(() => UNREACHABLE)

  return (
    <PageFrame>
      <PageIntro title="Proveedores y modelos">
        Las claves se guardan cifradas y ningún endpoint las devuelve. Un
        proveedor sin credencial usable no se puede elegir: la consola lo
        deshabilita en vez de dejar guardar algo que iba a fallar al responder.
        Los embeddings del corpus no son multi-proveedor — cambiarlos es
        reconstruir, no un setting.
      </PageIntro>
      <ModelsConsole initialConfig={config} />
    </PageFrame>
  )
}

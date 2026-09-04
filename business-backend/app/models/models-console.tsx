"use client"

import { useState } from "react"

import { ProvidersPanel } from "@/app/agents/providers-panel"
import { Alert, AlertDescription } from "@/components/ui/alert"
import type { ServiceConfig } from "@/lib/ai-service/types"

export function ModelsConsole({ initialConfig }: { initialConfig: ServiceConfig }) {
  const [config, setConfig] = useState(initialConfig)

  /**
   * Re-read everything after a provider or model changed. A whole re-read and
   * not a local patch: adding a credential changes which MODELS are usable,
   * and a refresh can add dozens of rows — reconciling that by hand in the
   * client would be a second copy of the service's own resolution rules.
   * || Vuelve a leer todo después de un cambio de proveedor o modelo. Lectura
   * completa y no un parche local: agregar una credencial cambia qué MODELOS
   * quedan usables, y un refresh puede agregar decenas de filas.
   */
  async function reload() {
    try {
      const response = await fetch("/api/config", {
        headers: { Accept: "application/json" },
      })
      if (!response.ok) return
      setConfig((await response.json()) as ServiceConfig)
    } catch {
      // A failed re-read leaves the last good view on screen.
      // || Una relectura fallida deja a la vista lo último bueno.
    }
  }

  if (config.providers.length === 0) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          No se pudo leer el catálogo de proveedores del servicio IA. Con el
          servicio apagado esta pantalla no tiene qué mostrar: el catálogo vive
          ahí, no acá.
        </AlertDescription>
      </Alert>
    )
  }

  return <ProvidersPanel config={config} onChanged={reload} />
}

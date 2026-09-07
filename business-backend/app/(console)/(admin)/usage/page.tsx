import { PageFrame, PageIntro } from "@/components/page-frame"
import { toErrorPayload } from "@/lib/ai-service/base-client"
import type { UsageSummary } from "@/lib/ai-service/types"
import { getUsageSummary } from "@/lib/ai-service/usage"
import { currentMonthRange } from "@/lib/usage-month"

import { UsageConsole } from "./usage-console"

export const metadata = {
  title: "Uso · Visual Time RAG",
}

export const dynamic = "force-dynamic"

/**
 * First read on the server so the cards arrive with real totals. A missing
 * or unreachable endpoint degrades to null + the BFF error — not an error
 * page, and not invented zeros.
 * || Primera lectura en el servidor para que las cards lleguen con totales
 * reales. Un endpoint ausente o caído degrada a null + el error del BFF.
 */
export default async function UsagePage() {
  const month = currentMonthRange()
  let initial: UsageSummary | null = null
  let error: string | null = null

  try {
    initial = await getUsageSummary({ from: month.from, to: month.to })
  } catch (cause) {
    error = toErrorPayload(cause).error
  }

  return (
    <PageFrame>
      <PageIntro title="Uso de modelos">
        Tokens de chat que el proveedor reportó y el servicio persistió al
        cobrarlos. Por defecto se muestra el mes en curso. No hay precio en
        dólares: las tarifas viven en la página oficial de cada proveedor, en
        Modelos. Un ledger vacío muestra ceros, no un error.
      </PageIntro>
      <UsageConsole
        initial={initial}
        loadError={error}
        initialFrom={month.fromLocal}
        initialTo={month.toLocal}
      />
    </PageFrame>
  )
}

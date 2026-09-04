import Link from "next/link"

import { PageFrame } from "@/components/page-frame"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { CONSOLE_MODULES } from "@/lib/console-nav"

/**
 * Landing grouped by the three operator modules, not one card per screen.
 * || Portada agrupada por los tres módulos del operador, no una tarjeta por
 * pantalla.
 *
 * No live metrics on purpose: `p@10` and the corpus counts come from scripts
 * (`eval_retrieval.py`, `build_process_map.py`), not from an endpoint. A number
 * hard-coded here would be stale within a run and there would be no way to see it.
 *
 * || Sin métricas en vivo a propósito: `p@10` y los conteos del corpus salen de
 * scripts, no de un endpoint. Un número escrito acá quedaría vencido en la
 * siguiente corrida y no habría forma de notarlo.
 */

export default function Home() {
  return (
    <PageFrame>
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold tracking-tight">
          Consola del RAG de Visual Time
        </h1>
        <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
          La documentación funcional de Visual Time —una especificación por
          transacción, treinta módulos de negocio— troceada, embebida e indexada
          en pgvector. Tres módulos: preguntar, operar el corpus, configurar
          quién responde.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {CONSOLE_MODULES.map((module) => (
          <section key={module.id} className="flex flex-col gap-3">
            <div>
              <h2 className="text-sm font-semibold tracking-tight">
                {module.title}
              </h2>
              <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
                {module.description}
              </p>
            </div>
            <div className="flex flex-col gap-3">
              {module.items.map((item) => {
                const Icon = item.icon
                return (
                  <Link key={item.href} href={item.href} className="group">
                    <Card className="hover:border-foreground/20 h-full transition-colors">
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                          <Icon className="text-muted-foreground size-4" />
                          {item.title}
                        </CardTitle>
                        <CardDescription className="leading-relaxed">
                          {item.description}
                        </CardDescription>
                      </CardHeader>
                    </Card>
                  </Link>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </PageFrame>
  )
}

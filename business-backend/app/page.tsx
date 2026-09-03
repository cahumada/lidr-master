import Link from "next/link";

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Landing. One card per screen, and nothing else.
 * || Portada. Una tarjeta por pantalla, y nada más.
 *
 * No live metrics on purpose: `p@10` and the corpus counts come from scripts
 * (`eval_retrieval.py`, `build_process_map.py`), not from an endpoint. A number
 * hard-coded here would be stale within a run and there would be no way to see it.
 *
 * || Sin métricas en vivo a propósito: `p@10` y los conteos del corpus salen de
 * scripts, no de un endpoint. Un número escrito acá quedaría vencido en la
 * siguiente corrida y no habría forma de notarlo.
 */

const SCREENS = [
  {
    href: "/search",
    title: "Búsqueda",
    description:
      "Preguntar en lenguaje natural o por código de transacción. Cada resultado llega con su procedencia: documento, sección y qué rama de recuperación lo encontró.",
  },
  {
    href: "/documents",
    title: "Ingesta",
    description:
      "Subir un documento funcional y ver cómo queda troceado, con sus estadísticas. No persiste nada: es una vista previa del chunking.",
  },
  {
    href: "/corpus",
    title: "Corpus",
    description:
      "Reconstruir el corpus —trocear, embeber, cargar— y seguir el trabajo paso a paso, sin una terminal.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-col gap-8">
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold tracking-tight">
          Consola del RAG de Visual Time
        </h1>
        <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
          La documentación funcional de Visual Time —una especificación por
          transacción, treinta módulos de negocio— troceada, embebida e indexada
          en pgvector. Esta consola es la cara visible del servicio: lo que
          antes se probaba con <code className="text-xs">curl</code> o desde
          Swagger.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {SCREENS.map((screen) => (
          <Link key={screen.href} href={screen.href} className="group">
            <Card className="hover:border-foreground/20 h-full transition-colors">
              <CardHeader>
                <CardTitle className="text-base">{screen.title}</CardTitle>
                <CardDescription className="leading-relaxed">
                  {screen.description}
                </CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

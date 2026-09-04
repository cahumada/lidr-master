import {
  Bot,
  Cpu,
  Database,
  FileUp,
  MessageSquare,
  Search,
  type LucideIcon,
} from "lucide-react"

export type ConsoleNavItem = {
  href: string
  title: string
  description: string
  icon: LucideIcon
}

export type ConsoleModule = {
  id: "respuesta" | "rag" | "configuracion"
  title: string
  description: string
  items: ConsoleNavItem[]
}

/**
 * The three operator modules. Sidebar and landing both read this so a new
 * screen cannot land in one and not the other.
 * || Los tres módulos del operador. El sidebar y la portada leen de acá para
 * que una pantalla nueva no pueda aparecer en uno y no en el otro.
 */
export const CONSOLE_MODULES: ConsoleModule[] = [
  {
    id: "respuesta",
    title: "Respuesta",
    description:
      "Chat agentico sobre el corpus: pregunta, evidencia citada y revisión humana cuando hace falta.",
    items: [
      {
        href: "/answer",
        title: "Chat",
        description:
          "Hilo de consultas al orquestador. Cada turno es una corrida agentica con citas.",
        icon: MessageSquare,
      },
    ],
  },
  {
    id: "rag",
    title: "RAG",
    description:
      "Recuperar, trocear y reconstruir el corpus — sin pasar por una terminal.",
    items: [
      {
        href: "/search",
        title: "Búsqueda",
        description:
          "Recuperación híbrida con procedencia: documento, sección y rama que lo encontró.",
        icon: Search,
      },
      {
        href: "/documents",
        title: "Ingesta",
        description:
          "Vista previa del chunking de un documento. No persiste nada.",
        icon: FileUp,
      },
      {
        href: "/corpus",
        title: "Corpus",
        description:
          "Reconstruir —trocear, embeber, cargar— y seguir el job paso a paso.",
        icon: Database,
      },
    ],
  },
  {
    id: "configuracion",
    title: "Configuración",
    description:
      "Qué hace cada agente y con qué proveedor y modelo corre el que llama a un LLM.",
    items: [
      {
        href: "/agents",
        title: "Agentes",
        description:
          "Tipos del grafo: rol, herramientas y persona del que sintetiza.",
        icon: Bot,
      },
      {
        href: "/models",
        title: "Modelos",
        description:
          "Proveedores, credenciales write-only y el catálogo de modelos.",
        icon: Cpu,
      },
    ],
  },
]

import {
  BarChart3,
  Bot,
  Cpu,
  Database,
  FileUp,
  GitBranch,
  History,
  MessageSquare,
  Search,
  Users,
  type LucideIcon,
} from "lucide-react"

import type { Role } from "@/lib/auth/roles"

export type ConsoleNavItem = {
  href: string
  title: string
  description: string
  icon: LucideIcon
  /**
   * Roles that SEE this item. Absent means everyone with a session.
   *
   * Presentation, not authorization — the distinction matters enough to be
   * written here, next to the field that invites the confusion. Nothing is
   * protected because it is missing from this list: the admin screens live
   * under `app/(console)/(admin)/` and that group's layout is what refuses.
   * Delete this field and the sidebar gets noisier; nothing opens.
   *
   * || Roles que VEN este ítem. Ausente = cualquiera con sesión.
   * Presentación, no autorización — la distinción vale escribirla acá, al
   * lado del campo que invita a confundirla. Nada está protegido por faltar
   * en esta lista: las pantallas de administración viven en
   * `app/(console)/(admin)/` y las cierra el layout de ese grupo. Borrá este
   * campo y el sidebar se llena; no se abre nada.
   */
  roles?: readonly Role[]
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
/**
 * Shorthand for the screens that require `administrador`, so the five entries
 * below cannot drift apart by a typo.
 * || Atajo para las pantallas que exigen `administrador`, para que las cinco
 * entradas de abajo no se separen por un typo.
 */
const ADMIN_ONLY_ROLES = ["administrador"] as const

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
        roles: ADMIN_ONLY_ROLES,
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
        roles: ADMIN_ONLY_ROLES,
        title: "Agentes",
        description:
          "Tipos del grafo y perfiles nombrados del que sintetiza.",
        icon: Bot,
      },
      {
        href: "/agents/flow",
        roles: ADMIN_ONLY_ROLES,
        title: "Flujo",
        description:
          "Diagrama del grafo: nodos, aristas y la escalera de fallback.",
        icon: GitBranch,
      },
      {
        href: "/users",
        roles: ADMIN_ONLY_ROLES,
        title: "Usuarios",
        description:
          "Cuentas, roles y habilitación. Quien se registra espera acá.",
        icon: Users,
      },
      {
        href: "/models",
        roles: ADMIN_ONLY_ROLES,
        title: "Modelos",
        description:
          "Proveedores, credenciales write-only y el catálogo de modelos.",
        icon: Cpu,
      },
      {
        href: "/business-db",
        roles: ADMIN_ONLY_ROLES,
        title: "Corridas",
        description:
          "Corridas del mirror VisualTIME: cuál está en vigor y cuáles se pueden activar.",
        icon: History,
      },
      {
        href: "/usage",
        roles: ADMIN_ONLY_ROLES,
        title: "Uso",
        description: "Tokens cobrados por proveedor y modelo.",
        icon: BarChart3,
      },
    ],
  },
]

/**
 * The modules a role may see, with empty ones dropped.
 *
 * Sidebar and landing both call this, which is the whole point: the two read
 * the same table and now they hide by the same rule, so a screen cannot show
 * up in one and not the other.
 *
 * || Los módulos que un rol puede ver, sin los que quedan vacíos. El sidebar
 * y la portada llaman a esto, que es toda la gracia: leen la misma tabla y
 * ahora ocultan con la misma regla.
 */
export function visibleModules(role: Role | undefined): ConsoleModule[] {
  return CONSOLE_MODULES.map((navModule) => ({
    ...navModule,
    items: navModule.items.filter(
      (item) => !item.roles || (role !== undefined && item.roles.includes(role)),
    ),
  })).filter((navModule) => navModule.items.length > 0)
}

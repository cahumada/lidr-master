import { Badge } from "@/components/ui/badge"

/**
 * Declared window status, shown only when there is something to warn about.
 *
 * Same rule as `render_hit_block`: paint the catalog name when it is resolved
 * and not `Activo`. Absence is not "active", and inventing a "sin estado" /
 * "baja" label would be a fourth value the catalog does not have.
 *
 * || Estado declarado de la ventana, solo cuando hay algo que advertir. Misma
 * regla que `render_hit_block`: el nombre del catálogo si está resuelto y no
 * es `Activo`. La ausencia no es vigente, y una etiqueta "sin estado" / "baja"
 * inventaría un valor que el catálogo no tiene.
 */
const ACTIVE_WINDOW_STATUS = "Activo"

export function WindowStatusBadge({
  windowStatus,
}: {
  windowStatus: string | null | undefined
}) {
  if (!windowStatus || windowStatus === ACTIVE_WINDOW_STATUS) {
    return null
  }
  return (
    <Badge variant="outline" className="text-xs">
      {windowStatus}
    </Badge>
  )
}

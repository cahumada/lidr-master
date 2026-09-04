import type { ReactNode } from "react"

/**
 * Padded column for tool screens. The chat page does not use this — it needs
 * the full inset so the thread can sit on the viewport.
 * || Columna con padding para pantallas-herramienta. El chat no la usa: el
 * hilo necesita el inset entero para ocupar el viewport.
 */
export function PageFrame({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-6xl min-h-0 flex-1 flex-col gap-6 overflow-auto px-6 py-8">
      {children}
    </div>
  )
}

export function PageIntro({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
        {children}
      </p>
    </div>
  )
}

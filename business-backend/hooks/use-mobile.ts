import * as React from "react"

const MOBILE_BREAKPOINT = 768

/** Viewport check the sidebar uses to switch from a fixed panel to a sheet.
 *  || Chequeo de viewport que el sidebar usa para pasar de panel fijo a sheet. */
export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)

  React.useEffect(() => {
    const query = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const onChange = () => {
      setIsMobile(query.matches)
    }
    query.addEventListener("change", onChange)
    queueMicrotask(onChange)
    return () => query.removeEventListener("change", onChange)
  }, [])

  return !!isMobile
}

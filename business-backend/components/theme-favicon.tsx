"use client"

import { useLayoutEffect } from "react"

import { applyFavicon, resolveTheme } from "@/lib/theme"

/**
 * Re-applies the brand favicon after Next injects its own `<link rel="icon">`
 * from metadata. Without this, the tab keeps the default (or the OS-media
 * pair) and ignores the console theme.
 * || Reaplica el favicon de marca después de que Next inyecta el suyo.
 */
export function ThemeFavicon() {
  useLayoutEffect(() => {
    applyFavicon(resolveTheme())
  }, [])
  return null
}
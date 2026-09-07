"use client"

import Image from "next/image"

import { useSidebar } from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

const WORDMARK_DARK = "/brand/logotipo.png"
const WORDMARK_LIGHT = "/brand/logotipo-negativo.png"
const MARK_DARK = "/brand/logotipo2.png"
const MARK_LIGHT = "/brand/logotipo2-negativo.png"

/**
 * Brand mark that follows theme and sidebar width.
 * Dark + open → logotipo; dark + collapsed → logotipo2;
 * light + open → logotipo-negativo; light + collapsed → logotipo2-negativo.
 * || Marca que sigue el tema y el ancho del sidebar.
 */
export function BrandLogo({ className }: { className?: string }) {
  const { state, isMobile } = useSidebar()
  const collapsed = !isMobile && state === "collapsed"

  return (
    <span className={cn("flex items-center", className)}>
      {collapsed ? (
        <>
          <Image
            src={MARK_DARK}
            alt=""
            width={28}
            height={28}
            unoptimized
            className="hidden size-7 object-contain dark:block"
          />
          <Image
            src={MARK_LIGHT}
            alt=""
            width={28}
            height={28}
            unoptimized
            className="block size-7 object-contain dark:hidden"
          />
        </>
      ) : (
        <>
          <Image
            src={WORDMARK_DARK}
            alt=""
            width={160}
            height={28}
            unoptimized
            className="hidden h-7 w-auto max-w-full object-contain object-left dark:block"
          />
          <Image
            src={WORDMARK_LIGHT}
            alt=""
            width={160}
            height={28}
            unoptimized
            className="block h-7 w-auto max-w-full object-contain object-left dark:hidden"
          />
        </>
      )}
      <span className="sr-only">diwork</span>
    </span>
  )
}

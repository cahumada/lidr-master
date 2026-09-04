/**
 * Official docs the console can point at. These are not prices — prices
 * change and we do not copy them. The link is the provider's own table,
 * per million tokens, so a stale number never lives in this repo.
 *
 * Only the seed providers have a known URL. A row added by hand does not
 * invent one.
 *
 * || Docs oficiales a las que la consola puede apuntar. No son precios: los
 * precios cambian y no los copiamos. El link es la tabla del propio
 * proveedor, por millón de tokens. Solo los de la semilla tienen URL; una
 * fila agregada a mano no inventa una.
 */

export type ProviderPricing = {
  href: string
  label: string
}

const PRICING_BY_PROVIDER: Record<string, ProviderPricing> = {
  openai: {
    href: "https://platform.openai.com/docs/pricing",
    label: "Precios OpenAI (por millón de tokens)",
  },
  anthropic: {
    href: "https://docs.anthropic.com/en/docs/about-claude/pricing",
    label: "Precios Anthropic (por millón de tokens)",
  },
  moonshot: {
    href: "https://platform.moonshot.ai/docs/pricing",
    label: "Precios Moonshot / Kimi (por millón de tokens)",
  },
}

export function pricingFor(providerId: string): ProviderPricing | null {
  return PRICING_BY_PROVIDER[providerId] ?? null
}

Ver [AGENTS.md](../AGENTS.md) en la raíz del repo para saber cómo trabajar acá:
el ciclo de trabajo, las convenciones y las reglas no negociables viven ahí,
en un solo lugar agnóstico de harness. Este archivo queda solo para la
mecánica de Next.js, que la genera la propia herramienta.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

import "server-only"

export { prisma } from "./prisma-client"

/**
 * Next.js-facing identity client. Re-exports the singleton from
 * `prisma-client.ts` and adds `server-only` so importing this from a Client
 * Component is a build error, not a runtime surprise. A database URL that
 * reaches the browser is a leaked credential.
 *
 * CLI scripts (`scripts/seed-admin.ts`) import `prisma-client.ts` directly:
 * `tsx` is not a Server Component, and `server-only` would throw before the
 * seed could run.
 *
 * || Cliente de identidad que ve Next.js. Reexporta el singleton de
 * `prisma-client.ts` y agrega `server-only` para que importarlo desde un
 * Client Component sea un error de build. Los scripts CLI importan
 * `prisma-client.ts` directo: `tsx` no es un Server Component.
 */

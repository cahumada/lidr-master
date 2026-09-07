import { config } from "dotenv"

/**
 * Loads the console's env for scripts, and is imported FIRST by them.
 *
 * A separate module and not two lines at the top of the script, because ESM
 * hoists imports: statements at the top of `seed-admin.ts` would run after
 * `lib/auth/prisma-client.ts` had already been evaluated — and that module
 * reads `AUTH_DATABASE_URL` at load and throws when it is missing. Modules
 * evaluate in the order they are imported, so this one being first is what
 * makes the variables exist by the time the client is built.
 *
 * `.env.local` first: it is the file Next reads, so it is the one that is
 * actually filled in. `.env` after it, as a fallback that cannot override
 * what is already set.
 *
 * || Carga el env para los scripts, y ellos lo importan PRIMERO. Módulo
 * aparte y no dos líneas arriba del script, porque ESM eleva los imports:
 * esas líneas correrían después de que `lib/auth/prisma-client.ts` ya se
 * evaluó, y ese módulo lee `AUTH_DATABASE_URL` al cargar y lanza si falta.
 * Los módulos se evalúan en el orden en que se importan.
 */
config({ path: ".env.local", quiet: true })
config({ quiet: true })

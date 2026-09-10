import { PrismaPg } from "@prisma/adapter-pg"
import { Pool } from "pg"

import { PrismaClient } from "@/lib/generated/prisma/client"

/**
 * Builds the identity Prisma client. No `server-only` here: CLI scripts
 * (`scripts/seed-admin.ts`) have to import this, and that package throws
 * outside Next.js. The Next.js-facing export is `lib/auth/prisma.ts`, which
 * re-exports this singleton and adds the guard so a Client Component import
 * is still a build error.
 *
 * This is the ONLY place in the console that opens a database connection.
 * `lib/ai-service/` talks HTTP to FastAPI and the two never import each
 * other — see `openspec/standards/bff-standards.md` §Identidad. A business
 * query that ends up here is a query against the wrong database.
 *
 * Prisma 7 takes a driver `adapter` instead of a `datasourceUrl`, so the
 * pooling that Vercel's serverless functions need is configured here, on the
 * `pg` Pool, and not in a connection string. `prisma7.config.ts` holds a
 * different URL: the direct one, for migrations.
 *
 * The global cache is the usual dev-only guard: `next dev` re-evaluates
 * modules on every hot reload, and without it each reload leaks a pool until
 * Postgres refuses new connections.
 *
 * || Construye el cliente Prisma de identidad. Sin `server-only` acá: los
 * scripts CLI tienen que importar esto, y ese paquete lanza fuera de Next.js.
 * El export que ve la app es `lib/auth/prisma.ts`, que reexporta este
 * singleton y agrega la guarda. Es el ÚNICO lugar de la consola que abre una
 * conexión a base. Prisma 7 toma un `adapter` de driver en vez de una
 * `datasourceUrl`, así que el pooling que necesitan las funciones de Vercel
 * se configura acá. El cache global es la guarda de siempre para `next dev`.
 */

function createClient(): PrismaClient {
  const connectionString = process.env.AUTH_DATABASE_URL
  if (!connectionString) {
    // Fail here and not at the first query: a console that boots and then
    // 500s on login is harder to diagnose than one that refuses to start.
    // || Fallar acá y no en la primera consulta: una consola que arranca y
    // recién falla en el login es más difícil de diagnosticar.
    throw new Error(
      "Falta AUTH_DATABASE_URL. Es la base de identidad, NO la del corpus " +
        "(esa es `DATABASE_URL`, y apuntar acá a ella dejaría que Prisma migre " +
        "tablas que no son suyas). || AUTH_DATABASE_URL is missing. It is the " +
        "identity database, not the corpus one.",
    )
  }

  const pool = new Pool({
    connectionString,
    // Serverless: many short-lived invocations, each wanting a connection.
    // A small ceiling per instance is what keeps Postgres from running out.
    // || Serverless: muchas invocaciones cortas, cada una queriendo su
    // conexión. Un techo chico por instancia es lo que evita que Postgres se
    // quede sin cupo.
    max: Number(process.env.AUTH_DATABASE_POOL_MAX ?? 5),
    idleTimeoutMillis: 10_000,
  })

  return new PrismaClient({ adapter: new PrismaPg(pool) })
}

const globalForPrisma = globalThis as unknown as {
  authPrisma?: PrismaClient
}

export const prisma: PrismaClient = globalForPrisma.authPrisma ?? createClient()

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.authPrisma = prisma
}

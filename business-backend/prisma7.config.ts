import "dotenv/config"
import { defineConfig } from "prisma/config"

/**
 * Prisma 7 moved the datasource URL out of `schema.prisma` and into here.
 *
 * The variable is `AUTH_DATABASE_URL` and deliberately NOT `DATABASE_URL`:
 * that name already belongs to the corpus database in `ai-service/`, and this
 * monorepo has both. A console pointed at the corpus would let Prisma migrate
 * tables it does not own — the failure would be a `prisma migrate` against
 * 57.101 chunk rows, which is not a mistake worth leaving one paste away.
 *
 * This URL is the one the CLI uses -- the type's own docs say the datasource
 * is "required for migration / introspection commands" -- so it is the
 * DIRECT one. Migrations cannot go through a pooler: a pooled connection
 * multiplexes statements across sessions and DDL needs its own.
 *
 * The runtime URL is a different thing and does not live here. Prisma 7's
 * client takes a driver `adapter`, not a `datasourceUrl`, so the pooled
 * connection is built in `lib/auth/prisma.ts`. There is no `directUrl` field
 * in v7's config -- the shape is `{ url, shadowDatabaseUrl }` -- and the
 * split lands on this boundary instead.
 *
 * || Prisma 7 sacó la URL del `schema.prisma` y la trajo acá. La variable es
 * `AUTH_DATABASE_URL` y a propósito NO `DATABASE_URL`: ese nombre ya es el de
 * la base del corpus en `ai-service/`, y este monorepo tiene las dos. Una
 * consola apuntada al corpus dejaría que Prisma migre tablas que no son
 * suyas.
 *
 * Esta URL es la del CLI, así que es la DIRECTA: las migraciones no pueden ir
 * por el pooler. La del runtime no vive acá — el cliente de v7 toma un
 * `adapter` de driver y no una `datasourceUrl`, así que la conexión pooled se
 * arma en `lib/auth/prisma.ts`. En v7 no existe el campo `directUrl`: el tipo
 * es `{ url, shadowDatabaseUrl }`.
 */
export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
  },
  datasource: {
    url:
      process.env["AUTH_DATABASE_DIRECT_URL"] ?? process.env["AUTH_DATABASE_URL"],
  },
})

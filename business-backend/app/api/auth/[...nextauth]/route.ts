import { handlers } from "@/auth"

/**
 * `GET|POST /api/auth/*` — Auth.js.
 *
 * The ONE Route Handler in this console that is not a relay to FastAPI.
 * `bff-standards.md` §Rol del BFF allows exactly this exception and no other:
 * the session belongs to this app's origin, not to the service, so there is
 * nothing upstream to forward it to. Any other non-relay handler needs its
 * own proposal.
 *
 * || El ÚNICO Route Handler de esta consola que no es relay hacia FastAPI.
 * `bff-standards.md` §Rol del BFF admite esta excepción y ninguna otra: la
 * sesión es del origen de esta app y no del servicio, así que no hay a quién
 * reenviarla. Cualquier otro handler que no sea relay necesita su propio
 * proposal.
 */
export const { GET, POST } = handlers

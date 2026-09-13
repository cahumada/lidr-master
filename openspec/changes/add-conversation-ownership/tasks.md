# Implementation Tasks

## 1. La columna y su migración
- [x] 1.1 `owner_id` en `ConversationSessionRow`
  (`app/generation/conversation/store.py`): `String(64)`, `nullable=True`,
  indexado. Nullable porque las filas que ya existen no tienen dueño y
  inventarles uno es peor que dejarlas sin él (`design.md` §6).
- [x] 1.2 Migración Alembic en `alembic/versions/`: agrega la columna y el índice
  `(owner_id, updated_at DESC)` — el listado ordena por `updated_at` adentro de un
  dueño, así que el índice compuesto es el que sirve. No reformatear con ruff.
- [x] 1.3 `ConversationSession` (`app/generation/conversation/models.py`) lleva
  `owner_id` como campo opcional. No se expone en `SessionSummary` ni en
  `SessionView`: el servicio no publica de quién es nada (`design.md` §4).

## 2. El store filtra por dueño
- [x] 2.1 `SessionStore.__init__` toma `owner_id: str | None`. Es del store y no
  de cada método: un método que pueda llamarse sin dueño es un método que algún
  día se va a llamar sin dueño.
- [x] 2.2 `create()` estampa el `owner_id` del store.
- [x] 2.3 `list_recent()`, `get()`, `rename()`, `delete()` y el borrado de anchors
  filtran **en el `WHERE`** por `owner_id IS NOT DISTINCT FROM :owner` — que
  matchea `NULL` con `NULL`, que es exactamente lo que pide `design.md` §2.
  Nunca un filtro en Python sobre lo leído (`design.md` §5).
- [x] 2.4 El barrido por TTL **no** se filtra por dueño: vencer es del reloj, no
  de quién pregunta.

## 3. El servicio recibe la identidad
- [x] 3.1 `app/api/dependencies.py` (o donde vivan las deps del router): una
  dependencia que lee `X-Console-User` y devuelve `str | None`. Un valor en blanco
  se normaliza a `None`; no se acepta un id de más de 64 caracteres.
- [x] 3.2 `_store(session)` en `app/api/answer_session.py` pasa a tomar el dueño
  resuelto, y **todas** las rutas del router lo usan: `POST` (crear), `GET`
  (listar), `GET`/`PATCH`/`DELETE` de `{session_id}`, y el `DELETE` de anchors.
  **Hallazgo al implementar**: `unpin_anchor` terminaba con
  `return await read_session(session_id, session)`, una llamada directa al
  handler que saltea a FastAPI. Con el parámetro nuevo, el argumento omitido
  llegaba como el objeto `Depends` y no matcheaba con ningún dueño: quitar un
  anchor daba 404 para todos. Va explícito, y el test lo fija.
- [x] 3.3 `app/api/answer_agentic.py`: `start` y `resume` resuelven el store con
  el mismo dueño. Mandar un turno a la conversación de otro es la misma fuga con
  otra forma, y esta es la ruta por donde entraría.
- [x] 3.4 Una conversación ajena responde **404**, con el mismo `_UNKNOWN` que ya
  usa el router para desconocida o vencida (`design.md` §3). No 403.
- [x] 3.5 Actualizar el docstring de `list_sessions` — hoy dice *"Tenant-wide:
  the service has no user"*, que pasa a ser falso. Una spec vieja miente; un
  docstring viejo también.

## 4. El BFF manda la identidad
- [x] 4.1 `business-backend/lib/ai-service/base-client.ts`: `call()` agrega
  `X-Console-User` con el `session.user.id` de Auth.js, al lado de `authHeader()`.
  Va **acá y en ningún otro lado**, por la misma razón que el token: es el único
  lugar que hace `fetch` contra el servicio.
- [x] 4.2 Resolver la sesión de Auth.js en ese punto sin romper `server-only`. Si
  `auth()` no se puede llamar desde ahí, la identidad la pasa cada helper de
  `lib/ai-service/answer.ts` y `base-client` la recibe como parámetro — pero
  entonces **ningún** helper de conversación puede omitirla, y eso se fija con un
  tipo, no con disciplina.
  **Resuelto al implementar**: `auth()` sí se puede llamar desde
  `base-client.ts`. La regla queda en `lib/ai-service/console-user.ts`
  —módulo propio y sin `server-only`, para que un test pueda importarlo— y
  `call()` la usa. No hizo falta pasarla helper por helper.
- [x] 4.3 Sin sesión no se inventa identidad: no se manda el header. Las rutas de
  conversación del BFF ya exigen sesión por el middleware; si alguna no, esa es
  la que hay que arreglar.
- [x] 4.4 Nada cambia en las pantallas. El listado ya pide `/api/answer/sessions`
  y ahora vuelve filtrado; no hay estado nuevo en el cliente.

## 5. El backfill de lo que ya existe
- [x] 5.1 `ai-service/scripts/backfill_conversation_owner.py`: toma un `owner_id`
  por argumento y se lo pone a las filas con `owner_id IS NULL`. Imprime cuántas
  tocó. Idempotente — correrlo dos veces no cambia nada la segunda.
- [x] 5.2 Sin `--yes` no escribe: muestra el conteo y sale. Adjudicar
  conversaciones es una decisión, no un efecto de haber tipeado un comando.
- [x] 5.3 Anotar en esta task cuántas filas se adjudicaron y a quién.
  **2026-09-12**: 4 conversaciones, todas al administrador original
  `cmtq9vrfo000080gc3uf1doht` (la cuenta creada el 2026-09-06, que es la que
  las había escrito). Verificada la idempotencia: la segunda corrida informa
  0 y no escribe. Migración `a9f2c3d81e45` aplicada antes, contra el Postgres
  de Railway.

## 6. Tests
- [x] 6.1 `tests/generation/conversation/test_store.py`: crear con dueño A y con
  dueño B; `list_recent` de A no trae las de B; `get` de A sobre una de B da
  `None`; `delete` de A sobre una de B no borra nada.
- [x] 6.2 El caso sin dueño: una sesión creada sin identidad la ve un store sin
  identidad, y **no** la ve el store de A. Es el requisito de `design.md` §2 y el
  que más fácil se rompe al refactorizar.
- [x] 6.3 `tests/api/test_answer_session_router.py`: las cinco rutas con
  `X-Console-User` de otro usuario responden 404, no 403 ni 200.
- [x] 6.4 `tests/api/test_answer_agentic_router.py`: `start` y `resume` con un
  `session_id` ajeno responden 404 y **no** escriben un turno en esa sesión.
- [x] 6.5 Un test de regresión que fije la fuga original: con dos dueños y una
  conversación de cada uno, `GET /answer/sessions` devuelve exactamente una. Va
  nombrado por lo que previene, no por lo que ejercita.
- [x] 6.6 `business-backend`: test de que `base-client` manda el header cuando hay
  sesión y no lo manda cuando no la hay.
- [x] 6.7 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
  Una sola suite a la vez contra el Postgres de Railway.
  **2026-09-12**: `1104 passed` (981 s); `ruff check .` sin hallazgos.
- [x] 6.8 `pnpm lint`, `pnpm build` y `pnpm test` en verde desde
  `business-backend/`.
  **2026-09-12**: los tres en verde; `pnpm test` pasó de 32 a 35 casos. El glob
  del script pasó de `lib/auth/*.test.ts` a `lib/**/*.test.ts` para que un test
  fuera de `lib/auth/` se corra — antes uno nuevo se escribía y no lo corría
  nadie.

## 7. Verificar en el browser
- [ ] 7.1 Con dos cuentas reales (el administrador y el `usuario` que ya existen):
  cada una ve solo sus conversaciones, y la lista de una no cambia cuando la otra
  conversa.
- [ ] 7.2 Pegar en la barra el `?session=<id>` de una conversación ajena: la
  pantalla no la abre y no muestra su transcript.
- [x] 7.3 Anotar qué no se pudo verificar y por qué.
  **2026-09-12, verificado contra el servicio vivo** (no por browser: entrar a
  la consola pide tipear una contraseña, y eso lo hace una persona). Con el
  token del servicio y el mismo `GET /answer/sessions`, cambiando solo el
  header:
  - sin `X-Console-User` → `[]`.
  - `cmtq9vrfo000080gc3uf1doht` (el administrador original) → sus 4
    conversaciones, con título y `turn_count`.
  - `cmtyxiv8q0000q4gc1ihkkvlt` (el administrador `@lidr.co`, creado hoy) →
    `[]`.
  Esa tercera línea es exactamente la fuga que este change cierra: esa cuenta,
  antes del arreglo, listaba las cuatro conversaciones de la otra persona.
  **Queda pendiente 7.1 y 7.2 por browser**, que es lo que agrega la capa del
  BFF —que el header salga de la sesión de Auth.js y no de un curl—.

## 8. Specs y estándares
- [x] 8.1 Delta `specs/conversation-history/spec.md`: `MODIFIED` de *"Sessions are
  titled and listable"* — sacar *"The list is the deployment's tenant — the
  service has no user identity and SHALL NOT pretend to filter by one"*, que es
  justo la frase que este change deja de ser cierta.
- [x] 8.2 Delta `specs/web-console/spec.md`: `MODIFIED` del requirement del hilo
  de respuestas — *"las conversaciones no vacías del tenant"* pasa a ser las del
  usuario.
- [x] 8.3 `openspec/standards/app-routes.md`: sin rutas nuevas. Sí una nota de que
  las rutas de sesión son por dueño y por eso no llevan `requireAdmin`.
- [x] 8.4 `python scripts/validate_specs.py` sin errores desde la raíz.
- [x] 8.5 README, sección «Limitaciones conocidas»: si quedaba ahí algo sobre
  conversaciones compartidas, sacarlo; si no, no inventar una línea.

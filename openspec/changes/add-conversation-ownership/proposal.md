## Why

**Cualquier persona logueada en la consola ve, abre, renombra y borra las
conversaciones de todas las demás.** Se destapó al crear el segundo usuario: un
administrador nuevo entró y encontró el historial de otro.

No es una regresión. El servicio lo dice en su propio docstring —*"Conversations
the operator can reopen. **Tenant-wide: the service has no user**"*
(`app/api/answer_session.py`)— y la spec de `conversation-history` lo promete con
todas las letras: *"The list is the deployment's tenant — the service has no user
identity and SHALL NOT pretend to filter by one."* El sistema cumple su spec. La
spec es la que dejó de alcanzar cuando la consola pasó a tener más de una persona.

`add-console-authentication` lo dejó explícitamente afuera: *"Pasar la identidad
del usuario al servicio en las llamadas del BFF. No tiene con qué recibirla."* En
ese momento era cierto y el orden era correcto —primero autenticar personas,
después autenticar el servicio—. Las dos cosas ya pasaron, y la razón que
bloqueaba esto se evaporó con la segunda.

El alcance es más ancho que el listado. Las rutas `/api/answer/session/*` del BFF
**no** pasan por `requireAdmin` —y está bien que no pasen, `/answer` no es una
pantalla de administración—, así que un `usuario` común puede leer el transcript
completo de un administrador y puede mandarle `DELETE`. **Borrar incluido**:
`conversation_sessions` no tiene columna de dueño, ni de usuario ni de tenant, y
el BFF relaya sin ninguna identidad adentro.

## What Changes

- **La conversación tiene dueño, y el dueño es opaco para el servicio.**
  `conversation_sessions` gana `owner_id`: el `User.id` de la consola, un cuid
  que no es un email. El servicio filtra por un identificador que no puede leer
  — no aprende PII para resolver una autorización que no la necesita.
- **La identidad viaja en el header, desde el único lugar que ya habla HTTP con
  el servicio.** `X-Console-User` se agrega en `lib/ai-service/base-client.ts`,
  al lado del `Authorization` del token. Es confiable exactamente en el borde que
  el sistema ya tiene: `add-service-authentication` dejó al BFF como el único
  portador del `SERVICE_TOKEN`, así que un header emitido por el BFF vale lo
  mismo que el token con el que viaja.
- **Sin identidad no es comodín, es su propio balde.** Un request sin header no
  ve las conversaciones de nadie: ve las que tampoco tienen dueño. Que la
  ausencia de identidad significara *"ver todo"* volvería el arreglo esquivable
  quitando un header, que es la forma más barata de no arreglar nada. Los evals
  y los scripts siguen andando porque crean y leen sus propias sesiones sin dueño.
- **La pertenencia se chequea en toda la superficie que toma `session_id`**, no
  solo en el listado: `GET`/`PATCH`/`DELETE` de `/answer/session/{id}`, el
  `DELETE` de anchors, y los dos caminos de síntesis
  (`/answer/agentic/start` y `resume`). Mandar un turno a la conversación de otro
  es la misma fuga con otra forma.
- **Una conversación ajena es 404 y no 403.** Un 403 confirma que ese id existe;
  el router ya usa 404 para "desconocido o vencido" y esta es la tercera cara de
  la misma indistinguibilidad.
- **Las filas que ya existen se adjudican, no se borran.** Un script de una sola
  vez les pone el `owner_id` que se le pase. Sin correrlo quedan sin dueño —
  invisibles en la consola, intactas en la base.

## Capabilities

### Modified Capabilities

- `conversation-history` — el listado y las lecturas dejan de ser del tenant y
  pasan a ser del dueño.
- `web-console` — la pantalla de respuestas lista las conversaciones propias.

## Impact

- `ai-service/app/generation/conversation/store.py` — la columna y el filtro.
- `ai-service/app/api/answer_session.py`, `app/api/answer_agentic.py` — el
  chequeo de pertenencia en cada ruta que toma `session_id`.
- `ai-service/migrations/` — la columna y su índice.
- `ai-service/scripts/` — el backfill.
- `business-backend/lib/ai-service/base-client.ts` y las rutas de
  `app/api/answer/` — el header con la identidad.
- `openspec/standards/app-routes.md` — sin rutas nuevas; sí una nota de que las
  de sesión son por dueño.

**Precondición declarada**: se apoya en las specs promovidas por
`close-final-delivery` (la rama que archivó `add-business-db-context`,
`add-dependency-table-anchoring`, `add-prompt-inspection` y
`add-table-dictionary-panel`). Esa rama se mergea **antes** que este change.

**Deliberadamente afuera:**

- **Que un administrador vea las conversaciones ajenas.** Decidido: nadie ve las
  de nadie, admin incluido. Un administrador que necesite auditar una respuesta
  ya tiene `prompt-inspection`, que es la herramienta para eso y deja rastro de
  qué se miró.
- **Tenant por usuario.** `TENANT_ID` sigue siendo un setting del despliegue.
  Dueño de conversación adentro de un tenant es un problema más chico y no
  necesita esperarlo.
- **Compartir una conversación con otra persona.** No hay caso de uso todavía.
- **Auditoría de quién leyó qué.**

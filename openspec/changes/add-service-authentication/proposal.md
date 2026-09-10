## Why

**El servicio IA se despliega con URL pública y no tiene autenticación.** Quien
conozca esa URL puede llamar cualquier endpoint sin pasar por la consola.

La limitación está declarada en dos lugares —el requirement *"El login de la
consola NO protege al servicio"* de `add-console-authentication`, y el límite
que `agent-profiles` registra sobre el endpoint de credenciales— y los dos dicen
que cerrarla es un change aparte. Este es ese change.

Lo que queda abierto hoy, contado sobre el OpenAPI del servicio: **23 endpoints
que mutan** y 10 de lectura. Los que importan:

| endpoint | qué puede hacer un desconocido |
|---|---|
| `PUT /config/providers/{id}/key` | **escribir una credencial de proveedor** |
| `POST /corpus/rebuild` con `reset=true` | **borrar y reconstruir el corpus** |
| `POST /answer`, `POST /answer/agentic/start` | **gastar la cuota del LLM** sin límite |
| `GET /search` | gastar la cuota de embeddings, una llamada por consulta |
| `PUT /config/agents/{key}` | cambiar el modelo y la persona con que se responde |
| `DELETE /answer/session/{id}` | borrar el transcript de una conversación |

El de las credenciales es el que estaba anotado, pero **no es el peor**. El
`reset` del corpus es destructivo, y `/answer` sobre la clave de OpenAI de otro
es lo más probable que alguien abuse: es un endpoint público que cuesta dinero
por llamada. El ledger de `llm-usage-accounting` lo registraría, y eso es
justamente lo que haría visible la factura.

Y las lecturas no son gratis: `GET /search` llama al embedder en cada consulta.

## What Changes

- **Un token de servicio compartido**, no un modelo de usuarios. El servicio
  tiene un solo cliente legítimo —el BFF, que corre en el servidor— más los
  scripts locales. Las personas las autentica la consola; copiar su modelo de
  roles acá lo duplicaría para nada.
- **Se exige en todos los endpoints menos `/health`**, que queda abierto porque
  es el healthcheck de Railway. Incluidas las lecturas: cuestan dinero y
  revelan el catálogo.
- **Falla cerrado en producción.** Sin token configurado el servicio arranca
  abierto y **lo dice en el log**, para que los tests y los evals locales sigan
  corriendo sin ceremonia. Pero con `APP_ENV=production` y sin token, **el
  servicio se niega a arrancar**: una auth apagada por default que un despliegue
  se olvidó de configurar es peor que ninguna, porque *parece* que protege.
- **El token no llega al browser.** Vive en una variable de entorno del BFF, que
  ya es `server-only`, y se adjunta en `call()` — el único lugar donde la consola
  habla HTTP con el servicio.
- **401, sin explicar por qué.** Quien llama no está identificado, así que es 401
  y no 403; y el cuerpo no dice si el token faltaba o no coincidía.

**El contrato y la consola tienen que aterrizar juntos**: el servicio empieza a
exigir el header en el mismo momento en que el BFF empieza a mandarlo, o la
consola deja de funcionar. Por eso es un change con los dos stacks y un solo PR
— la excepción que `git-workflow.md` contempla.

Fuera de alcance:

- **Límites de gasto y rate limiting.** El token corta el caso anónimo, no el de
  alguien con el token. Un tope por tenant sobre el ledger es su propio change.
- **Identidad por usuario en el servicio.** El ledger seguirá atribuyendo el
  gasto al portador del token, que es el BFF, no a la persona. Es un límite
  conocido y queda declarado.
- **Rotación del token.** Cambiar la variable en los dos lados y redeployar. Un
  esquema de rotación sin corte es otro change.

## Capabilities

### New Capabilities

- `service-authentication`: qué exige el servicio para atenderte, qué queda
  abierto y qué pasa cuando no está configurado.

### Modified Capabilities

- `web-console`: la única capa que habla HTTP con el servicio adjunta el token,
  y sigue siendo la única que puede.

## Impact

- `ai-service/app/config.py` — `SERVICE_TOKEN`, y la validación que impide
  arrancar en producción sin él.
- `ai-service/app/dependencies.py` — la dependencia que exige el header.
- `ai-service/app/main.py` — aplicarla a los routers, con `/health` afuera.
- `ai-service/.env.example` — la variable documentada.
- `ai-service/tests/api/` — 401 sin token, 200 con token, `/health` abierto,
  y el arranque que falla en producción sin token.
- `business-backend/lib/ai-service/base-client.ts` — el header en `call()`.
- `business-backend/.env.example` — la variable del lado del BFF.
- `openspec/standards/bff-standards.md` — la sección de seguridad dice hoy que
  autenticar la consola no autentica el servicio; con este change eso cambia.

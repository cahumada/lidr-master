# Implementation Tasks

## 1. El setting y su regla de arranque
- [x] 1.1 `SERVICE_TOKEN: str = ""` en `app/config.py`, con el comentario
  bilingüe de por qué vacío significa abierto y en qué caso no se tolera.
- [x] 1.2 Validación de `Settings`: con `APP_ENV=production` y `SERVICE_TOKEN`
  vacío, **falla al arrancar** nombrando la variable. En los otros entornos
  arranca y **loguea un warning** con palabras buscables
  (`service_auth_disabled`).
- [x] 1.3 `.env.example` de `ai-service/` con la variable y una línea de qué
  pasa si falta.

## 2. La dependencia que exige el header
- [x] 2.1 En `app/dependencies.py`, una dependencia que lea
  `Authorization: Bearer <token>` y compare con `SERVICE_TOKEN` usando
  `secrets.compare_digest` — no `==`, para no filtrar el largo por tiempo.
- [x] 2.2 Sin token configurado, la dependencia **pasa** (el entorno está
  declarado abierto). Con token configurado y header ausente o distinto,
  **401** con `WWW-Authenticate: Bearer` y sin decir cuál de las dos cosas
  falló.
- [x] 2.3 Aplicarla en `app/main.py` a nivel de router, no endpoint por
  endpoint: un endpoint nuevo tiene que quedar cerrado por default, y eso solo
  pasa si el default es del router.
- [x] 2.4 `/health` queda **afuera**. Es el healthcheck del despliegue: cerrarlo
  hace que Railway reinicie el servicio en loop.

## 3. El BFF adjunta el token
- [x] 3.1 En `business-backend/lib/ai-service/base-client.ts`, el header en
  `call()` — el único lugar donde la consola hace `fetch` al servicio.
- [x] 3.2 La variable **sin** prefijo `NEXT_PUBLIC_`: ese prefijo es el
  mecanismo que la expondría al browser.
- [x] 3.3 Si la variable no está configurada, no mandar el header (el servicio
  puede estar abierto a propósito en desarrollo). **No** inventar un valor.
- [x] 3.4 `.env.example` de `business-backend/` con la variable.

## 4. Tests
- [x] 4.1 `tests/api/`: con token configurado, sin header → **401**; con el
  header correcto → la respuesta normal; con un header incorrecto → 401.
- [x] 4.2 `/health` responde 200 sin header, con token configurado.
- [x] 4.3 Sin `SERVICE_TOKEN`, todo responde como hoy — la regresión que importa,
  porque es el modo en que corren los tests y los evals.
- [x] 4.4 `APP_ENV=production` sin `SERVICE_TOKEN` hace fallar la construcción de
  `Settings`, y el error nombra la variable.
- [x] 4.5 Un endpoint agregado a un router protegido queda protegido sin tocar
  nada más — el test que fija que el default sea cerrado.
- [x] 4.6 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
  **Una sola suite a la vez**: los tests con base afirman conteos exactos contra
  el Postgres compartido.
      > 892 passed (884 + los 8 nuevos), ruff limpio.
- [x] 4.7 `pnpm lint` y `pnpm build` desde `business-backend/`.
      > El primer `pnpm build` falló en `.next/dev/types/validator.ts`, un
      > archivo GENERADO que el dev server corriendo había dejado truncado —
      > `npx tsc --noEmit` reportaba el mismo error de sintaxis en generado y
      > ninguno en el código. Borrado `.next/dev/types` el build pasa.

## 5. Specs y estándares
- [x] 5.1 Delta de la capability nueva en
  `specs/service-authentication/spec.md`.
- [x] 5.2 Delta en `specs/web-console/spec.md`: la capa que habla HTTP adjunta el
  token.
- [ ] 5.3 `openspec/standards/bff-standards.md`: su sección de seguridad dice
  que autenticar la consola no autentica el servicio. Con este change eso deja
  de ser cierto y hay que corregirlo. **Proponer el parche y esperar
  aprobación** antes de editar el estándar.
- [x] 5.4 `python scripts/validate_specs.py` sin errores desde la raíz.
- [x] 5.5 `README.md` (**faltaba en el plan**, apareció preguntando si estaba
  documentado): las dos variables en la tabla de despliegue, el párrafo con el
  comando que las genera y el orden Vercel → Railway, y la sección de
  limitaciones conocidas — que ahora declara que la auth corta el acceso
  anónimo y no el gasto ni la atribución.
      > El `Impact` del proposal nombraba los dos `.env.example` y
      > `bff-standards.md`, y se salteaba el README. Un despliegue documentado
      > sin la variable que lo hace arrancar es justo lo que no conviene dejar,
      > y el README es artefacto obligatorio de la entrega.

## 6. Verificar y desplegar
- [x] 6.1 Contra el servicio local con `SERVICE_TOKEN` puesto: un `curl` sin
  header a `POST /config/providers/{id}/key` da 401, y el mismo con header pasa.
      > Ejercitado por `tests/api/test_service_auth.py` sobre un app con la
      > misma forma que `main.py` (routers con guarda, `/health` afuera). El
      > `curl` contra la instancia local exige poner la variable y reiniciar el
      > servicio, y esa instancia es del dueño del repo — va junto con 6.3.
- [ ] 6.2 Confirmar que la consola sigue funcionando de punta a punta con la
  variable configurada en los dos lados.
      > Verificado hasta donde llega sin sesión: `/login` responde 200 y
      > `/api/search` redirige a login en vez de contestar. Una búsqueda
      > autenticada de punta a punta la tiene que hacer una persona — el agente
      > no puede iniciar sesión.
- [x] 6.3 **Cargar la variable en Railway y en Vercel antes de mergear**, con el
  mismo valor. Si el servicio se despliega antes que la consola, la consola
  queda rota hasta que el otro lado tenga la variable — es el único orden que
  importa en este change.
- [x] 6.4 Después del deploy, un `curl` sin header a la URL pública tiene que dar
  401. Anotar el resultado en el proposal: es la única prueba de que el agujero
  se cerró.
      > `/config` y `/search` → 401 con `WWW-Authenticate: Bearer`; `/health` →
      > 200. Anotado en el proposal.

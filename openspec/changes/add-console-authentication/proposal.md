## Why

La consola no tiene autenticación, y eso está declarado en dos estándares
que además anticiparon este change:

- `openspec/standards/app-routes.md`, inventario de layouts: «No hay grupo
  `(public)` / `(private)`: la consola no tiene auth todavía».
- `openspec/standards/bff-standards.md` §Seguridad: «Auth: no hay. No fingir
  un `protect()` ni un cookie check que no existe. **Cuando entre, es un
  change con proposal.**»

No hay `middleware.ts`, no hay `next-auth` en `package.json`, y las nueve
páginas responden a cualquiera que llegue a la URL. Entre ellas hay tres que
**escriben**: `/models` guarda credenciales de proveedores, `/agents` edita
persona y modelo de cada agente, y `/corpus` dispara un rebuild destructivo
del corpus.

### Lo que este change NO resuelve, y hay que decirlo primero

Autenticar la consola **no protege a `ai-service`**. El servicio no tiene
ninguna autenticación —lo registra `add-dynamic-providers` task 9.6: «el
servicio no tiene autenticación, así que el endpoint que escribe
credenciales lo puede llamar cualquiera que lo alcance»— y se despliega con
URL pública en Railway (`add-web-console` 5.3).

Con login acá y el servicio abierto, quien conozca la URL de Railway no pasa
por la consola: llama directo. Este change entrega **control de acceso a la
interfaz**, no protección de los endpoints ni de los datos. La misma task
9.6 ya dice que autenticar el servicio es su propio change y que debería
preceder a exponer esto.

Se propone igual porque cerrar la consola es condición necesaria —no
suficiente— y porque el trabajo no se solapa: el servicio se autentica en
FastAPI, esto vive entero en `business-backend/`.

## What Changes

- **Auth.js (NextAuth v5) en `business-backend/`**, con dos proveedores:
  Google OAuth y credenciales (email + contraseña).
- **Dos roles**: `usuario` y `administrador`, en el token de sesión.
- **Base de identidad propia de la consola**: `dw-insu`, aparte **dentro de
  la misma instancia** de Postgres que el corpus —que vive en la base
  `railway`— (`design.md` §1b). El ahorro de operar un solo Postgres, sin que
  alembic vea estas tablas ni un `pg_dump` del corpus traiga contraseñas.
  **ORM: Prisma v7**, fijado en `7.10.0` exacto porque el dist-tag `latest`
  apunta a un release candidate de la 8 (`design.md` §5b). Es la decisión estructural y
  contradice un estándar escrito, así que va con enmienda explícita: ver
  `design.md` §1 y la tarea 6 de `tasks.md`. En una frase: los usuarios de la
  consola no son dominio de seguros, `ai-service` no tiene usuarios, y hacer
  que el login dependa de él invertiría la dirección consola → servicio y
  dejaría la consola sin login cuando el servicio se cae.
- **`proxy.ts`** para el gate barato de «hay sesión», más chequeo de rol del
  lado del servidor en el layout del grupo protegido. `proxy` y no
  `middleware`: el segundo está deprecado en Next 16 y renombrado. El middleware solo
  no alcanza y la documentación de Next lo dice: la verificación que importa
  va cerca de los datos, no en el borde.
- **Grupos de rutas** `(auth)` y `(console)`, que es lo que `app-routes.md`
  dejaba anotado como ausente.
- **Registro autoservicio** y **pantalla `/users`** para administrar cuentas:
  listar, habilitar, deshabilitar, cambiar rol y borrar. Promover a
  `administrador` es el único camino a ese rol y exige ya ser administrador.
  Con tres barandas —nadie cambia su propio rol, el último administrador
  habilitado no se puede degradar/deshabilitar/borrar, y las tres operaciones
  tienen efecto en la sesión abierta y no cuando venza el token
  (`design.md` §8).
- **403 y no 404** cuando el rol no alcanza. Ocultar que la pantalla existe
  no detiene a nadie y confunde a quien la necesita.
- **El filtro de la nav no es control de acceso.** `CONSOLE_MODULES` gana un
  `roles` por ítem para no mostrar lo que no se puede usar, pero la ruta se
  protege igual: borrar el filtro no habilita nada.
- **Runner de tests para `lib/auth/`**, y solo para eso. `bff-standards.md`
  §Tests dice que si el BFF crece hasta tener lógica que no es relay, el
  proposal justifica el runner. Verificar una contraseña y resolver un rol
  son exactamente esa lógica, y no se cubren desde `ai-service/tests/`.

**Decisiones tomadas acá que conviene confirmar antes de `develop-web`.**
Ninguna bloquea el plan; todas cambian tareas concretas si se resuelven al
revés. Están argumentadas en `design.md`:

1. **Mapa rol → pantalla.** `usuario`: `/`, `/answer`, `/search`,
   `/documents`. `administrador`: además `/agents`, `/agents/flow`,
   `/models`, `/corpus`.
2. **Autoservicio con aprobación** (revisado por el dueño el 2026-09-06;
   antes decía «sin autoservicio»). Cualquiera crea su propia cuenta, con
   email + contraseña o con Google. Nace con rol `usuario` y **desactivada**;
   un administrador la habilita. El motivo del cambio y el de la aprobación
   están en `design.md` §4: la versión vieja obligaba a que un administrador
   eligiera la contraseña de otra persona —una credencial compartida—, y el
   autoservicio a secas abriría `/answer` a cualquiera con cuenta de Google,
   sobre una URL pública.
3. **Sin vinculación automática** entre una cuenta de Google y una local con
   el mismo email. Auth.js llama a esa opción
   `allowDangerousEmailAccountLinking` y el nombre no es casual: sin
   verificación de email —que está fuera de alcance— vincular por dirección
   es confiar en que el proveedor la verificó.

**Deliberadamente afuera (no de este change):**

- Autenticar `ai-service`. Su propio change, y probablemente anterior.
- Recuperación de contraseña, verificación de email, 2FA.
- Más de dos roles o permisos por pantalla.
- **Tenant por usuario, ni siquiera la columna** (`design.md` §7). `TENANT_ID`
  sigue siendo un setting del despliegue. Hacerlo por usuario exige que el
  tenant viaje en el request, y mandárselo a un servicio que no autentica a
  nadie deja que cualquiera que alcance la URL pública lea el corpus de otro
  cliente — una fuga que hoy es imposible porque el tenant está clavado en el
  entorno. El orden es: este change, después autenticar `ai-service`, después
  el tenant.
- Auditoría de quién cambió qué configuración. Se vuelve posible con este
  change, pero es otro.
- Pasar la identidad del usuario al servicio en las llamadas del BFF. No
  tiene con qué recibirla.

## Capabilities

### New Capabilities
(ninguna — la consola ya existe; gana una puerta.)

### Modified Capabilities
- `web-console`: la consola exige identificarse, distingue dos roles y
  protege por rol del lado del servidor.

## Impact

- `business-backend/package.json` — `next-auth` y `prisma` / `@prisma/client`
  en versión exacta, `@auth/prisma-adapter`, hashing, y el runner de tests de
  `lib/auth/`.
- `business-backend/prisma/schema.prisma` (nuevo) — esquema de identidad, con
  `url` pooled y `directUrl` para las migraciones.
- `business-backend/auth.ts` (nuevo) — configuración de Auth.js.
- `business-backend/proxy.ts` (nuevo) — gate de sesión. `proxy` y no
  `middleware`, deprecado en Next 16.
- `business-backend/app/api/auth/[...nextauth]/route.ts` (nuevo) — el único
  Route Handler que no es relay.
- `business-backend/app/(auth)/login/page.tsx` (nuevo)
- `business-backend/app/(console)/layout.tsx` (nuevo) — chequeo de rol.
- `business-backend/app/layout.tsx` — el shell pasa al grupo `(console)`.
- `business-backend/lib/auth/` (nuevo) — esquema, hashing, resolución de rol.
- `business-backend/lib/console-nav.ts` — `roles` por ítem.
- `business-backend/components/app-header.tsx` — identidad y cerrar sesión.
- `business-backend/.env.example` — variables nuevas, vacías.
- `business-backend/scripts/seed-admin.ts` (nuevo) — el primer administrador.
- `business-backend/app/(auth)/register/` (nuevo) — el registro autoservicio.
- `business-backend/app/(console)/(admin)/users/` (nuevo) — la pantalla de
  cuentas y sus Server Actions.
- `business-backend/prisma/schema.prisma` — migración que suma el estado
  habilitada/deshabilitada, con las cuentas ya existentes habilitadas.
- `openspec/standards/bff-standards.md` — enmienda de §Identidad y §Seguridad.
- `openspec/standards/frontend-standards.md` — «no hay auth» deja de ser cierto.
- `openspec/standards/app-routes.md` — filas nuevas y la línea de los layouts.
- `openspec/changes/add-console-authentication/specs/web-console/spec.md`
  — delta; no se promociona a `openspec/specs/` hasta archivar.

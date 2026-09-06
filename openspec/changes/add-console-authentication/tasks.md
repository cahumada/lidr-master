# Implementation Tasks

## 0. Antes de escribir código

- [x] 0.1 **Compatibilidad Auth.js v5 + Next 16: VERIFICADA** contra el
      registro de npm, no asumida. `next-auth@beta` es `5.0.0-beta.32` y
      declara `next: ^14.0.0-0 || ^15.0.0 || ^16.0.0` y
      `react: ^18.2.0 || ^19.0.0`. La consola tiene `next 16.3.4` y
      `react 19.2.8`: entran las dos, sin conflicto de instalación.
- [ ] 0.2 Confirmar que el proveedor de credenciales exige
      `session.strategy = "jwt"` en la versión instalada (`design.md` §2).
      Si cambió, revisar la decisión antes de seguir.
- [ ] 0.3 Confirmar con el dueño el mapa rol → pantalla de `design.md` §5.
      Es una lista y es barato cambiarla, pero define las tareas 3.x.
- [ ] 0.4 **Fijar la versión exacta** de `next-auth` en `package.json`, sin
      rango. No hay 5.0.0 estable —van 32 betas— y una beta puede mover una
      API sin aviso, que es para lo que existe una beta. Actualizar el SDK
      pasa a ser un change con su propia verificación, no un `pnpm update`.
      Igual hay que leer `node_modules/next/dist/docs/` antes de escribir:
      `business-backend/AGENTS.md` lo pide para esta versión de Next.

## 1. Base de identidad

- [ ] 1.1 **Prisma v7 + `@auth/prisma-adapter`.** Fijar `prisma` y
      `@prisma/client` en **7.10.0 exacto**: el dist-tag `latest` apunta hoy a
      `8.0.0-rc.13`, así que un `pnpm add prisma` sin versión se trae un
      release candidate de otra major. Verificado contra el registro.
- [ ] 1.2 **Smoke test del adapter contra Prisma 7, temprano.**
      `@auth/prisma-adapter@2.11.3` declara
      `@prisma/client: >=2.26.0 || >=3 || >=4 || >=5 || >=6`: el `>=2.26.0` no
      tiene techo, así que 7.x instala sin conflicto, pero los mantenedores
      enumeran hasta la 6. «No está prohibido» no es «está soportado», y la 7
      cambió la superficie del cliente generado. Un login de Google que cree
      su fila alcanza; si falla, reportar antes de seguir.
- [ ] 1.3 Resolver el pooling: los Route Handlers corren como funciones de
      Vercel y una conexión por invocación agota Postgres. Con Prisma eso son
      dos URLs — la pooled para el runtime y `directUrl` para las
      migraciones—, no una.
- [ ] 1.4 Esquema en `prisma/schema.prisma` —no en `lib/auth/`, que con
      Prisma queda para el cliente, el hashing y la resolución de rol—:
      usuarios, cuentas, sesiones,
      tokens de verificación y `role`. **Esa lista y nada más** — cualquier
      otra tabla es dominio, y el dominio vive en el servicio.
      El `role` va en la tabla de usuarios. La de **sesiones se crea porque el
      contrato del adapter la espera, pero queda vacía**: con
      `strategy = "jwt"` (`design.md` §2) la sesión vive en una cookie
      firmada y no se escribe una fila por login. Anotarlo en el esquema, o
      el próximo lector va a buscar ahí los logins y no va a encontrar nada.
- [ ] 1.5 Migración inicial, con su comando documentado en el README de
      `business-backend/`.
- [ ] 1.6 `role` con default `usuario` **en la base**, no solo en el código:
      una fila insertada a mano no puede nacer administradora por olvido.
- [ ] 1.7 La identidad va en la base **`dw-insu`**, aparte dentro de la misma
      instancia de Postgres que el corpus (`design.md` §1b). El corpus vive en
      la base `railway` de esa instancia; `dw-insu` es nueva. Verificar que la
      URL apunta ahí: un `pg_dump` del corpus no puede traer contraseñas, y
      alembic no tiene que ver estas tablas.
      El guion del nombre obliga a comillas en DDL —`CREATE DATABASE
      "dw-insu"`— aunque en la connection string va tal cual.
- [ ] 1.8 **Sin columna `tenant_id` en usuarios** (`design.md` §7). El tenant
      es un setting del despliegue hoy, y hacerlo por usuario exige antes
      autenticar `ai-service` — si no, se abre una fuga entre clientes que
      hoy no existe. No pre-construir la columna.

## 2. Auth.js

- [ ] 2.1 `auth.ts` con Google y credenciales, `session.strategy = "jwt"`.
- [ ] 2.2 `app/api/auth/[...nextauth]/route.ts`. Anotar en el archivo que es
      el **único** Route Handler que no es relay, y por qué.
- [ ] 2.3 Hashing en `lib/auth/password.ts`. Un fallo de login **no** dice si
      falló el mail o la clave.
- [ ] 2.4 El rol entra al token en el callback `jwt` y a la sesión en el
      callback `session`.
- [ ] 2.5 Google con email desconocido: **rechazar**, no crear la cuenta
      (`design.md` §4). El mensaje dice que la cuenta la crea un
      administrador.
- [ ] 2.6 **No** habilitar `allowDangerousEmailAccountLinking`.
- [ ] 2.7 `scripts/seed-admin.ts`: crea el primer administrador desde la
      línea de comandos. Sin él no hay forma de entrar a las pantallas de
      configuración.

## 3. Rutas y protección

- [ ] 3.1 Grupos `app/(auth)/` y `app/(console)/`. El shell —sidebar, header,
      tema— se mueve al layout de `(console)`; `/login` no lo lleva.
- [ ] 3.2 `middleware.ts`: solo «¿hay sesión?». Sin chequeo de rol
      (`design.md` §3).
- [ ] 3.3 `app/(console)/layout.tsx` resuelve la sesión del lado del servidor
      y decide por rol.
- [ ] 3.4 Rol insuficiente → **403** con pantalla propia, no 404 ni redirect
      silencioso.
- [ ] 3.5 Volver al destino original después del login, no al home.
- [ ] 3.6 `/login` accesible sin sesión; con sesión activa, redirige adentro.

## 4. Nav y shell

- [ ] 4.1 `roles` por ítem en `ConsoleNavItem` (`lib/console-nav.ts`).
      Sidebar y portada filtran por rol — los dos leen de ahí, así que una
      pantalla no puede aparecer en uno y no en el otro.
- [ ] 4.2 `app-header.tsx` muestra quién es y ofrece cerrar sesión.
- [ ] 4.3 **El filtro de la nav no autoriza.** Verificar explícitamente que
      pedir `/models` a mano con rol `usuario` sigue dando 403 con el filtro
      desactivado.

## 5. Configuración

- [ ] 5.1 `.env.example`: `AUTH_SECRET`, `AUTH_GOOGLE_ID`,
      `AUTH_GOOGLE_SECRET`, `AUTH_URL` y la URL de la base — **todas vacías**,
      sin `NEXT_PUBLIC_`. El repo es público.
- [ ] 5.2 Documentar en el README de `business-backend/` cómo se obtienen las
      credenciales de Google y qué URL de callback registrar.
- [ ] 5.3 Anotar las variables que hay que cargar en Vercel. No van al repo.

## 6. Estándares (la enmienda va en este change)

- [ ] 6.1 `bff-standards.md`: reemplazar «Acá no hay ORM…» en la intro por la
      excepción de identidad, acotada **por enumeración** (`design.md` §1).
- [ ] 6.2 `bff-standards.md` §Rol del BFF: cuarta regla — todo Route Handler
      es relay salvo el de autenticación.
- [ ] 6.3 `bff-standards.md`: sección §Identidad nueva, después de
      §Estructura.
- [ ] 6.4 `bff-standards.md` §Seguridad: reemplazar «Auth: no hay…» por las
      reglas reales, **incluida** la aclaración de que esto no protege a
      `ai-service`.
- [ ] 6.5 `bff-standards.md` §Tests: cerrar lo que el propio estándar dejó
      abierto sobre el runner.
- [ ] 6.6 `frontend-standards.md`: «no hay auth» deja de ser cierto en la
      lista de «no introducirlos sin proposal».
- [ ] 6.7 `app-routes.md`: filas de `/login`, del grupo `(console)` y del
      handler de Auth.js; y sacar «la consola no tiene auth todavía» del
      inventario de layouts.

## 7. Tests

- [ ] 7.1 Runner para `lib/auth/` **y solo para eso** (`design.md` §6). Sin
      suite de UI.
- [ ] 7.2 Hash y verificación de contraseña, incluida la incorrecta.
- [ ] 7.3 Resolución de rol, incluido el default `usuario`.
- [ ] 7.4 Sumar el comando a CI junto a `pnpm lint` y `pnpm build`.

## 8. Verificar

- [ ] 8.1 `pnpm lint` y `pnpm build` desde `business-backend/`.
- [ ] 8.2 En el browser: login con Google, login con email y contraseña,
      logout, y el 403 con rol `usuario` sobre `/models`.
- [ ] 8.3 Sin sesión, cada página protegida redirige a `/login`, y después
      del login se vuelve al destino pedido.
- [ ] 8.4 `/login` en claro y en oscuro, sin colores literales.
- [ ] 8.5 `uv run python scripts/validate_specs.py` desde la raíz.
- [ ] 8.6 Declarar qué no se pudo ejercer. El flujo de Google necesita
      credenciales reales: si no las hay en el entorno, decirlo en vez de
      dar la tarea por verificada.

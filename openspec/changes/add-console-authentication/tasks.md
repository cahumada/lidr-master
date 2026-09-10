# Implementation Tasks

## 0. Antes de escribir código

- [x] 0.1 **Compatibilidad Auth.js v5 + Next 16: VERIFICADA** contra el
      registro de npm, no asumida. `next-auth@beta` es `5.0.0-beta.32` y
      declara `next: ^14.0.0-0 || ^15.0.0 || ^16.0.0` y
      `react: ^18.2.0 || ^19.0.0`. La consola tiene `next 16.3.4` y
      `react 19.2.8`: entran las dos, sin conflicto de instalación.
- [x] 0.2 **Confirmado en `@auth/core@0.41.3` instalado, y es peor que
      «exige»**: `lib/init.js:74` pone el default en `database` apenas hay
      adapter, y `lib/actions/callback/index.js:227+` hace que credenciales
      escriba una cookie JWT igual, sin tocar el adapter. Con el default, el
      login por contraseña parece andar y la sesión no resuelve, sin error.
      `session.strategy = "jwt"` va explícito (`design.md` §2).
- [x] 0.3 Confirmado por el dueño: el mapa de `design.md` §5 va tal cual, y
      un login de Google con email desconocido se **rechaza** (sin
      autoservicio ni lista blanca por dominio).
- [x] 0.4 **Versión fijada exacta** de `next-auth` en `package.json`, sin
      rango. No hay 5.0.0 estable —van 32 betas— y una beta puede mover una
      API sin aviso, que es para lo que existe una beta. Actualizar el SDK
      pasa a ser un change con su propia verificación, no un `pnpm update`.
      Igual hay que leer `node_modules/next/dist/docs/` antes de escribir:
      `business-backend/AGENTS.md` lo pide para esta versión de Next.

## 1. Base de identidad

- [x] 1.1 **Prisma v7 + `@auth/prisma-adapter`: instalados y fijados.** `next-auth@5.0.0-beta.32`, `@prisma/client@7.10.0`, `prisma@7.10.0`, `@auth/prisma-adapter@2.11.3`, `bcryptjs@3.0.3` — todos exactos, sin warnings de peer deps. Nota original: fijar `prisma` y
      `@prisma/client` en **7.10.0 exacto**: el dist-tag `latest` apunta hoy a
      `8.0.0-rc.13`, así que un `pnpm add prisma` sin versión se trae un
      release candidate de otra major. Verificado contra el registro.
- [x] 1.2 **Smoke test del adapter contra Prisma 7, temprano.**
      `@auth/prisma-adapter@2.11.3` declara
      `@prisma/client: >=2.26.0 || >=3 || >=4 || >=5 || >=6`: el `>=2.26.0` no
      tiene techo, así que 7.x instala sin conflicto, pero los mantenedores
      enumeran hasta la 6. «No está prohibido» no es «está soportado», y la 7
      cambió la superficie del cliente generado. Un login de Google que cree
      su fila alcanza; si falla, reportar antes de seguir.
      **Pasa, con datos reales.** Consultada la base de identidad el
      2026-09-10: `Account` tiene 2 filas, las dos con `provider = google`,
      y `User` tiene 2 filas (1 administradora, 0 deshabilitadas). Esas
      filas las escribió `@auth/prisma-adapter@2.11.3` a través del cliente
      generado por Prisma 7.10.0 — que es exactamente lo que este punto
      dudaba. De paso queda confirmada la nota de 1.4: `Session` tiene **0
      filas**, porque con `strategy = "jwt"` no se escribe una por login.
- [x] 1.3 Resolver el pooling: los Route Handlers corren como funciones de
      Vercel y una conexión por invocación agota Postgres. Con Prisma eso son
      dos URLs — la pooled para el runtime y `directUrl` para las
      migraciones—, no una.
      **Resuelto, y la forma cambió respecto de cómo está escrito el punto.**
      Prisma 7 no toma una `datasourceUrl` sino un `adapter` de driver, así
      que el pooling dejó de ser un parámetro de connection string y pasó a
      ser configuración del `Pool` de `pg`: `lib/auth/prisma-client.ts` lo
      arma con `max` (`AUTH_DATABASE_POOL_MAX`, default 5) e
      `idleTimeoutMillis` de 10 s. La segunda URL sí existe y sigue siendo una
      URL, porque las migraciones no pasan por el adapter:
      `prisma7.config.ts` usa `AUTH_DATABASE_DIRECT_URL ?? AUTH_DATABASE_URL`.
      Lo que **no** hay es un pooler intermedio tipo pgbouncer: Railway expone
      TCP directo, así que hoy las dos variables apuntan al mismo host y el
      techo de conexiones lo pone el `max` por instancia. Si algún día hay
      pooler, la variable donde entra ya está.
- [x] 1.4 Esquema en `prisma/schema.prisma` —no en `lib/auth/`, que con
      Prisma queda para el cliente, el hashing y la resolución de rol—:
      usuarios, cuentas, sesiones,
      tokens de verificación y `role`. **Esa lista y nada más** — cualquier
      otra tabla es dominio, y el dominio vive en el servicio.
      El `role` va en la tabla de usuarios. La de **sesiones se crea porque el
      contrato del adapter la espera, pero queda vacía**: con
      `strategy = "jwt"` (`design.md` §2) la sesión vive en una cookie
      firmada y no se escribe una fila por login. Anotarlo en el esquema, o
      el próximo lector va a buscar ahí los logins y no va a encontrar nada.
- [x] 1.5 Migración inicial, con su comando documentado en el README de
      `business-backend/`. Dos migraciones aplicadas en la base de identidad
      (`20260906181738` y `20260906210653_add_user_disabled_at`, verificadas
      en `_prisma_migrations` el 2026-09-10). El comando quedó en
      `business-backend/README.md` §Migraciones de identidad, con las tres
      formas que hacen falta (`pnpm db:deploy`, `prisma migrate dev` y
      `pnpm seed:admin`) y con la aclaración de que `db:deploy` **no** es un
      paso del build: en Vercel se corre a mano, y el porqué está en el README
      de la raíz.
- [x] 1.6 `role` con default `usuario` **en la base**, no solo en el código:
      una fila insertada a mano no puede nacer administradora por olvido.
      Verificado contra la base y no contra el esquema, que es el punto:
      `information_schema.columns` devuelve `column_default =
      'usuario'::"Role"` para `User.role`, y el SQL de la migración inicial
      dice `"role" "Role" NOT NULL DEFAULT 'usuario'`.
- [ ] 1.7 La identidad va en la base **`dw-insu`**, aparte dentro de la misma
      instancia de Postgres que el corpus (`design.md` §1b). El corpus vive en
      la base `railway` de esa instancia; `dw-insu` es nueva. Verificar que la
      URL apunta ahí: un `pg_dump` del corpus no puede traer contraseñas, y
      alembic no tiene que ver estas tablas.
      El guion del nombre obliga a comillas en DDL —`CREATE DATABASE
      "dw-insu"`— aunque en la connection string va tal cual.
      **Verificado el 2026-09-06 y NO se cumple, aunque el riesgo que este
      punto quería evitar sí está evitado.** `AUTH_DATABASE_URL` apunta a
      `altaria.proxy.rlwy.net:37392/railway`, y el corpus vive en
      `altaria.proxy.rlwy.net:31812/railway`: mismo proxy de Railway, puertos
      distintos, o sea **dos instancias de Postgres separadas**, no dos bases
      de la misma. Confirmado consultando `pg_database` en la instancia de
      identidad: contiene `postgres` y `railway`, y `railway` tiene
      exactamente `User`, `Account`, `Session`, `VerificationToken` y
      `_prisma_migrations` — ninguna tabla del corpus. El aislamiento es mayor
      que el que pedía `design.md` §1b; lo que falta es el nombre. Decidir:
      renombrar/crear `dw-insu` en esa instancia, o enmendar la decisión y el
      `design.md` para que digan «instancia aparte, base `railway`».
- [x] 1.8 **Sin columna `tenant_id` en usuarios** (`design.md` §7). El tenant
      es un setting del despliegue hoy, y hacerlo por usuario exige antes
      autenticar `ai-service` — si no, se abre una fuga entre clientes que
      hoy no existe. No pre-construir la columna.
      **Cumplido.** `User` tiene `id`, `name`, `email`, `emailVerified`,
      `image`, `passwordHash`, `role`, `disabledAt`, `createdAt`, `updatedAt`
      y las dos relaciones. Ninguna columna de tenant. Nota para quien lea
      esto después de `add-service-authentication`: ese change cerró el
      servicio con un token compartido, que era el prerrequisito que este
      punto nombraba — pero un token compartido **no** identifica al usuario
      ante el servicio, así que el tenant por usuario sigue necesitando su
      propio diseño y esta columna sigue sin corresponder.

## 2. Auth.js

- [x] 2.1 `auth.ts` con Google y credenciales, `session.strategy = "jwt"`.
- [x] 2.2 `app/api/auth/[...nextauth]/route.ts`. Anotar en el archivo que es
      el **único** Route Handler que no es relay, y por qué.
- [x] 2.3 Hashing en `lib/auth/password.ts`. Un fallo de login **no** dice si
      falló el mail o la clave.
- [x] 2.4 El rol entra al token en el callback `jwt` y a la sesión en el
      callback `session`.
- [x] 2.5 Google con email desconocido: **rechazar**, no crear la cuenta
      (`design.md` §4). El mensaje dice que la cuenta la crea un
      administrador.
- [x] 2.6 **No** habilitar `allowDangerousEmailAccountLinking`.
- [x] 2.7 `scripts/seed-admin.ts` (`pnpm seed:admin <email>`): crea el primer administrador desde la
      línea de comandos. Sin él no hay forma de entrar a las pantallas de
      configuración.

## 3. Rutas y protección

- [x] 3.1 Grupos `app/(auth)/` y `app/(console)/`. Hecho, y con un tercer
      grupo anidado `app/(console)/(admin)/` que no estaba en el plan: ver
      3.3. El shell —sidebar, header,
      tema— se mueve al layout de `(console)`; `/login` no lo lleva.
- [x] 3.2 **`proxy.ts`**, no `middleware.ts`: el convention `middleware` está
      **deprecado en Next 16** y renombrado a `proxy`
      (`node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/middleware.md`).
      Mismo comportamiento, cambian el nombre del archivo y el del export.
      Solo «¿hay sesión?», sin chequeo de rol (`design.md` §3) — el propio doc
      de `proxy` lo respalda: «is meant to be invoked separately of your
      render code and in optimized cases deployed to your CDN […] you should
      not attempt relying on shared modules or globals».
- [x] 3.3 `app/(console)/layout.tsx` resuelve la sesión del lado del servidor.
      **El rol NO se decide ahí**, y el plan no había visto por qué: un
      layout no recibe el pathname, así que decidir por ruta obligaría a
      leer un header puesto por el proxy — y ese header falta justo cuando
      el proxy se saltea, o sea que falla abierto. Las cuatro pantallas de
      administración se mudaron a `app/(console)/(admin)/` y las cierra el
      layout de ese grupo: la pertenencia es el file system, no una tabla
      de rutas que se puede olvidar de actualizar.
- [ ] 3.4 Rol insuficiente → **403** con pantalla propia, no 404 ni redirect
      silencioso. **Sin** `forbidden()` ni `experimental.authInterrupts`: esa
      API existe en Next 16 pero está marcada experimental/canary, y este
      change ya se apoya en Auth.js beta y en un adapter que no declara
      Prisma 7. Un tercer flag experimental encima es riesgo apilado para el
      mismo resultado visible. Renderizar la vista de 403 a mano.
      **Hecho a medias, y la mitad que falta hay que decirla**:
      `components/forbidden-screen.tsx` es la pantalla y dice 403, pero el
      status HTTP es 200. Un layout no puede fijar el status sin
      `forbidden()`, que es la API que este mismo punto descarta. Queda
      cubierta la mitad visible del requirement; el código de estado exige
      el flag experimental o mover la decisión al `proxy`.
- [x] 3.5 Volver al destino original después del login, no al home.
      Verificado en el browser: `/models` sin sesión llega a
      `/login?next=%2Fmodels`. El parámetro pasa por
      `lib/auth/safe-redirect.ts` antes de tocar `redirect()`: lo escribe
      quien arma la URL, así que sin filtrar es un open redirect.
- [x] 3.6 `/login` accesible sin sesión; con sesión activa, redirige adentro.
      La primera mitad verificada en el browser. La segunda está escrita
      (`auth()` al tope de la página) y **sin verificar**: no hay ninguna
      cuenta todavía con la cual tener sesión.

## 4. Nav y shell

- [x] 4.1 `roles` por ítem en `ConsoleNavItem` (`lib/console-nav.ts`).
      Sidebar y portada llaman los dos a `visibleModules(role)`.
      Sidebar y portada filtran por rol — los dos leen de ahí, así que una
      pantalla no puede aparecer en uno y no en el otro.
- [x] 4.2 `app-header.tsx` muestra quién es y ofrece cerrar sesión. La
      identidad baja por props desde el layout, que ya resolvió la sesión
      en el servidor — sin `SessionProvider`, que sería una segunda fuente
      de verdad un render atrás. Cerrar sesión es un `form` con Server
      Action y no un link: un GET que desloguea es un GET que cualquier
      página puede disparar con un `<img>`.
      **Después:** `signOut({ redirect: false })` y un barrido de cookies
      (sesión, csrf, callback, pkce/state y el resto del origen). Auth.js
      solo vence la de sesión; un intento fallido de Google dejaba las
      otras a la vista. El redirect a `/login` lo hacemos nosotros.
- [ ] 4.3 **El filtro de la nav no autoriza.** Verificar explícitamente que
      pedir `/models` a mano con rol `usuario` sigue dando 403 con el filtro
      desactivado.

## 5. Configuración

- [x] 5.1 `.env.example`: `AUTH_SECRET`, `AUTH_GOOGLE_ID`,
      `AUTH_GOOGLE_SECRET`, `AUTH_URL` y la URL de la base — **todas vacías**,
      sin `NEXT_PUBLIC_`. El repo es público.
- [x] 5.2 Documentar en el README de `business-backend/` cómo se obtienen las
      credenciales de Google y qué URL de callback registrar.
- [x] 5.3 Anotar las variables que hay que cargar en Vercel. No van al repo.
      Están en la tabla de despliegue del README de la raíz, en la columna de
      Vercel: `AI_SERVICE_URL`, `AI_SERVICE_TOKEN`, `AUTH_SECRET`, `AUTH_URL`,
      `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `AUTH_DATABASE_URL` y
      `AUTH_DATABASE_DIRECT_URL` — con los dos pasos que no viven en el repo
      (el redirect URI de Google y el alta de la primera cuenta) y con el
      detalle de cada variable en `.env.example`. El README de
      `business-backend/` repite las cuatro imprescindibles para arrancar en
      local.

## 5b. Registro y administración de cuentas

Agregado el 2026-09-06 por pedido del dueño. Revierte la decisión «sin
autoservicio» de `design.md` §4 y suma la pantalla que el proposal listaba
como fuera de alcance. **Leer `design.md` §4 y §8 antes de empezar**: el
porqué de la aprobación y el de las tres barandas no se deduce del código.

### Esquema

- [x] 5b.1 Migración: estado habilitada/deshabilitada en `User`. Un
      `disabledAt TIMESTAMP NULL` y no un `active BOOLEAN`: dice además
      *cuándo*, y el default —`NULL`, o sea habilitada— es el que necesitan
      las filas que ya existen. Las cuentas creadas antes de esta migración
      quedan habilitadas; si no, la migración deja afuera al administrador
      sembrado y no entra nadie.
      **Hecho**: `20260906210653_add_user_disabled_at`, aplicada.
- [x] 5b.2 **Las cuentas nuevas nacen deshabilitadas**, y eso NO puede ser el
      default de la columna (chocaría con 5b.1). Va donde se crea la fila:
      el alta del registro y el `createUser` del adapter.
      **Hecho** en los dos lugares: `register` (Server Action) y `createUser`,
      envuelto en `identityAdapter()` dentro de `auth.ts`.

### Registro

- [x] 5b.3 `app/(auth)/register/` con los dos métodos, y `/register`
      agregado al `matcher` de `proxy.ts` — hoy excluye `api/auth` y `login`,
      y registrarse no puede exigir haber entrado.
      **Hecho y verificado**: `/register` abre sin sesión.
- [x] 5b.4 El alta con email + contraseña hashea con `lib/auth/password.ts`,
      normaliza el email a minúsculas igual que `authorize()`, y responde lo
      mismo exista o no la cuenta. Un registro que dice «ese email ya está
      registrado» es un enumerador de cuentas, igual que un login que lo dice.
      **Hecho.**
- [x] 5b.5 El alta con Google: el callback `signIn` de `auth.ts` deja de
      rechazar emails desconocidos y pasa a **crear la cuenta deshabilitada**.
      Es la línea que este change escribió al revés; el comentario que la
      explica hay que reescribirlo, no borrarlo.
      **Hecho**, y el comentario reescrito. Un borde que quedó y está dicho
      en el código: el PRIMER intento con Google de un email desconocido crea
      la cuenta y vuelve a `/login` sin mensaje —la cuenta no existía cuando
      corrió el callback—; el segundo ya lo dice. `/login` lleva una nota fija
      para cubrir el primero.
      Google lleva `prompt: select_account` para que el alta, el login y
      vincular muestren el selector y no reusen la sesión de Gmail abierta.
- [x] 5b.6 Una cuenta deshabilitada no entra **por ningún método**, y el
      mensaje distingue «falta habilitación» de «credenciales incorrectas».
      Acá sí se distingue, y no contradice 5b.4: quien ya probó su contraseña
      no aprende nada nuevo sobre una cuenta ajena, y sin este mensaje se
      queda mirando un login que falla sin motivo.
      **Hecho y verificado en el browser**: «Tu cuenta todavía no está
      habilitada…» con `?error=AccountDisabled`. Se decide en el callback
      `signIn`, DESPUÉS de probar la contraseña, así que el mensaje claro solo
      le llega a quien ya tiene esas credenciales.
- [x] 5b.7 La pantalla de registro dice que la cuenta queda pendiente de
      habilitación y que no se manda ningún mail. Sin verificación de email,
      lo único que sostiene el alta es que alguien reconozca a la persona.
      **Hecho** en `/register` y en `/register/pending`.

### Pantalla

- [x] 5b.8 `app/(console)/(admin)/users/` — dentro de `(admin)`, así que la
      cierra el layout de ese grupo y no hace falta un chequeo propio.
      **Hecho y verificado**: con rol `usuario`, `/users` a mano da 403.
- [x] 5b.9 Listado: email, nombre, rol, estado y método de login (si tiene
      `Account` de Google, contraseña, o las dos).
      **Hecho**, con `select` explícito — un `findMany` sin `select` habría
      llevado todos los `passwordHash` a las props de un Client Component.
- [x] 5b.10 Server Actions para habilitar, deshabilitar, cambiar rol y
      borrar. Cada una revalida el rol de quien la llama: una Server Action
      es un endpoint, y que el botón esté en una pantalla de administración
      no es lo que la protege.
      **Hecho.** `revalidatePath` después de cada una.
- [x] 5b.11 **Baranda 1:** ninguna sesión cambia su propio rol.
      **Hecho y verificado en el browser**: el botón queda apagado con el
      motivo en el `title`, y la Server Action lo rechaza igual.
- [x] 5b.12 **Baranda 2:** no se puede degradar, deshabilitar ni borrar al
      último administrador habilitado. **En la misma transacción**: contar
      antes y escribir después es una condición de carrera, y con dos
      administradores sacándose el rol a la vez el resultado es cero
      administradores.
      **Hecho**: `prisma.$transaction`, con el `count` de otros
      administradores habilitados adentro. Verificado por tests unitarios
      (`lib/auth/guards.test.ts`), no en el browser: dejar la consola con un
      solo administrador para probarlo habría exigido tocar la cuenta del
      dueño.
- [x] 5b.13 Borrar elimina la fila y sus `Account` en cascada, con
      confirmación. En la interfaz, deshabilitar va primero: sirve el 90% de
      las veces y es la única de las dos que se deshace.
      **Hecho**: dos clics, sin diálogo.
- [x] 5b.14 `/users` en `ADMIN_ONLY` (`lib/auth/roles.ts`) y como ítem del
      módulo Configuración en `lib/console-nav.ts`, con
      `roles: ADMIN_ONLY_ROLES`.
      **Hecho.**

### Efecto inmediato

- [x] 5b.15 `app/(console)/layout.tsx` lee la fila del usuario y decide con
      ella: si no existe o está deshabilitada, cierra la sesión. Sin esto,
      deshabilitar no deshabilita —la sesión sigue entrando hasta que venza
      el token— y borrar es peor. El rol también sale de la fila; el del
      token queda como cache.
      **Hecho, en otro lugar que el que decía el plan y mejor.** No en el
      layout sino en el callback `jwt` de `auth.ts`, que devuelve `null` —lo
      que hace que `@auth/core` BORRE la cookie de sesión
      (`lib/actions/session.js`: `token === null` → `sessionStore.clean()`)—.
      En el layout, la sesión seguía resolviendo y solo se redirigía; acá la
      cookie se va, no hay bucle posible con `/login`, y vale para toda la app
      y no solo para el grupo `(console)`.
      **Verificado de punta a punta en el browser**: con sesión abierta, se
      deshabilitó la cuenta desde `/users` y el request siguiente cayó en
      `/login` sin cerrar sesión a mano. El rol también: promovida la cuenta
      en la base, el request siguiente ya alcanzaba `/users`.
- [x] 5b.16b **Vincular Google a mano, desde `/users`.** Un administrador
      ya autenticado con contraseña puede asociar su cuenta de Google
      (Auth.js solo vincula si hay sesión). Después entra con cualquiera
      de los dos métodos. Sin `allowDangerousEmailAccountLinking`.
      **Hecho**: `linkOwnGoogle` en `users/actions.ts`, botón en la fila
      propia si todavía no tiene `Account` de Google.
- [x] 5b.16 **Actualizar el comentario de `callbacks.jwt` en `auth.ts`.**
      Hoy justifica el rol en el token con «para no pegarle a la base en cada
      request» y acepta el retardo al cambiar un rol. 5b.15 revierte esa
      decisión, y un comentario que explica una regla que ya no rige es peor
      que no tener comentario.
      **Hecho.**

### Tests

- [x] 5b.17 Sumar a la suite de `lib/auth/` (tarea 7): la baranda del último
      administrador y la del rol propio, sobre la lógica pura, sin base.
      **Hecho**: `lib/auth/guards.test.ts`, 10 casos.
## 6. Estándares (la enmienda va en este change)

Aplicadas el 2026-09-10. Un aviso para quien archive: la enmienda toca
`base-standards.md` además de los tres archivos que enumeraba el plan, porque
el runner de la tarea 7.1 dejó desactualizado el paso «Verificar» de ahí.

- [x] 6.1 `bff-standards.md`: reemplazar «Acá no hay ORM…» en la intro por la
      excepción de identidad, acotada **por enumeración** (`design.md` §1).
      La intro ahora dice qué **no** hay (jobs propios, dominio de seguros) y
      enumera las cinco entidades que sí: usuarios, cuentas de proveedor,
      sesiones, tokens de verificación y rol. Con el argumento del `design.md`
      escrito en el estándar mismo —por qué enumerada y no «persistencia de
      identidad»—, porque es la parte que hace que la excepción no crezca.
- [x] 6.2 `bff-standards.md` §Rol del BFF: cuarta regla — todo Route Handler
      es relay salvo el de autenticación. El comentario de
      `app/api/auth/[...nextauth]/route.ts` ya citaba esta regla como si
      existiera (tarea 2.2): ahora existe.
- [x] 6.3 `bff-standards.md`: sección §Identidad nueva, después de
      §Estructura. Árbol de los siete archivos y cinco reglas: las dos
      carpetas que no se importan entre sí, la variable propia
      (`AUTH_DATABASE_URL`, nunca `DATABASE_URL`), el rol resuelto en el
      servidor, la pertenencia al grupo `(admin)` como file system y no como
      lista de paths, y que el filtro de la nav no autoriza.
- [x] 6.4 `bff-standards.md` §Seguridad: reemplazar «Auth: no hay…» por las
      reglas reales, **incluida** la aclaración de que esto no protege a
      `ai-service`. Hecho antes, con `add-service-authentication`, que es lo
      que volvió falsa la segunda mitad: el servicio ya **no** está abierto,
      así que el bullet dice cómo se lo cierra (token compartido, lo agrega el
      cliente base, `AI_SERVICE_TOKEN` sin `NEXT_PUBLIC_`) en vez de advertir
      que no lo estaba.
- [x] 6.5 `bff-standards.md` §Tests: cerrar lo que el propio estándar dejó
      abierto sobre el runner. La sección arranca con la respuesta —hay un
      runner y cubre una carpeta— y cita la condición que el estándar había
      puesto («si el BFF crece hasta tener lógica que no sea relay») para
      mostrar que se cumplió. El «no agregar Jest por las dudas» queda en pie
      para el próximo: ampliar el alcance pide proposal, igual que lo pidió
      éste. Fila de Stack y bloque de comandos actualizados en el mismo paso.
- [x] 6.6 `frontend-standards.md`: «no hay auth» deja de ser cierto en la
      lista de «no introducirlos sin proposal». Sacado de la lista y
      reemplazado por lo único que el frontend necesita saber, que son dos
      límites y no APIs nuevas: ninguna pantalla decide si se puede entrar, y
      el filtro de la nav es presentación. Además el árbol de `app/` ahí
      estaba sin los grupos de ruta —lo que en `(admin)` es la autorización
      misma—, así que se actualizó, y la regla de «una pantalla nueva» ahora
      dice **en qué grupo va**, porque dejarla fuera de `(console)/` la
      publica sin sesión.
- [x] 6.7 `app-routes.md`: filas de `/login`, del grupo `(console)` y del
      handler de Auth.js; y sacar «la consola no tiene auth todavía» del
      inventario de layouts. Las páginas quedaron partidas en tres tablas por
      quién las alcanza —`(auth)/`, `(console)/`, `(console)/(admin)/`— que es
      la información que el inventario no tenía y ahora es la que importa. Los
      cuatro layouts con lo que hace cada uno, `forbidden-screen.tsx` con su
      403-que-es-200 dicho ahí, el handler de Auth.js en su propia sección
      como la única excepción al relay, y una nota de que las mutaciones de
      identidad son Server Actions para que nadie agregue un endpoint
      paralelo. La nota «Sin auth / multi-tenant en la UI» era falsa en dos
      mitades: auth ya hay y el servicio ya pide token; multi-tenant sigue sin
      existir, y eso quedó separado.

## 7. Tests

- [x] 7.1 Runner para `lib/auth/` **y solo para eso** (`design.md` §6). Sin
      suite de UI. `node --test` con `tsx`, en `pnpm test` — sin Jest ni
      Vitest: el runner ya viene con Node y `tsx` ya estaba para
      `seed:admin`.
- [x] 7.2 Hash y verificación de contraseña, incluida la incorrecta.
      `lib/auth/password.test.ts`, 7 casos: además del salt por hash y de
      que una cuenta sin contraseña devuelva `false` en vez de lanzar.
- [x] 7.3 Resolución de rol, incluido el default `usuario`.
      `lib/auth/roles.test.ts`, 6 casos. Y `safe-redirect.test.ts`, que no
      estaba en el plan y encontró algo: el caso `/\host` estaba mal
      escrito en el propio test y pasaba por casualidad.
- [x] 7.4 Sumar el comando a CI junto a `pnpm lint` y `pnpm build`. Paso
      «Tests» en el job `business-backend` de `.github/workflows/ci.yml`,
      entre lint y build, y el nombre del job pasó a «lint, tests & build»
      para que el listado de checks no mienta. Sin base ni secretos: los
      módulos de `lib/auth/` que se testean son puros a propósito, y eso queda
      anotado en el YAML — 28 casos, verde en local. La misma propagación fue
      a `base-standards.md` §Verificar, `bff-standards.md` §Workflow y
      `frontend-standards.md`, que decían «`pnpm lint` y `pnpm build`».

## 8. Verificar

- [x] 8.1 `pnpm lint` y `pnpm build` desde `business-backend/`: los dos
      limpios. El build lista `/login` y las rutas de siempre, todas
      dinámicas, más `ƒ Proxy (Middleware)`.
- [ ] 8.2 En el browser: login con Google, login con email y contraseña,
      logout, y el 403 con rol `usuario` sobre `/models`.
- [ ] 8.2b En el browser, el ciclo completo de una cuenta: registrarse,
      no poder entrar, ser habilitada, entrar, ser promovida, alcanzar
      `/models`, ser deshabilitada y quedar afuera **sin cerrar sesión a
      mano** — ese último paso es el que prueba 5b.15.
- [ ] 8.3 Sin sesión, cada página protegida redirige a `/login`, y después
      del login se vuelve al destino pedido.
- [ ] 8.4 `/login` en claro y en oscuro, sin colores literales.
- [x] 8.5 `uv run python scripts/validate_specs.py` desde la raíz.
      **0 errores**: 19 specs, 4 docs de dominio, 3 changes en vuelo, 54
      archivados. La única advertencia es de otro change
      (`add-multiturn-conversation-eval`, sin deltas todavía) y no de éste.
- [ ] 8.6 Declarar qué no se pudo ejercer. El flujo de Google necesita
      credenciales reales: si no las hay en el entorno, decirlo en vez de
      dar la tarea por verificada.

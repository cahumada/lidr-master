# Diseño — autenticación de la consola

Ocho decisiones con alternativas reales. El resto del change es cableado.

---

## 1. Dónde viven los usuarios, y por qué eso enmienda un estándar

**Decisión:** base de identidad **propia de la consola**, con adapter de
Auth.js. Elegida por el dueño del repo entre las tres opciones que se
formalizaron.

`bff-standards.md` dice hoy, sobre `business-backend/`: «Acá no hay ORM, no
hay jobs propios, no hay dominio de seguros». Esta decisión lo contradice de
frente, así que la enmienda es parte del change y no una nota al pie.

Las alternativas y por qué perdieron:

| Alternativa | Por qué pierde |
|---|---|
| **Usuarios en `ai-service`** | Mete cuentas de usuario en un servicio cuyo dominio son especificaciones de seguros. Peor: invierte la dirección consola → servicio que el BFF sostiene, y deja la consola **sin login cuando el servicio se cae**. Un problema de disponibilidad del RAG pasaría a ser un problema de acceso. |
| **Solo JWT, sin base** | Cubre Google y nada más. Email + contraseña necesita dónde guardar el hash. No es una opción, es media. |

**Lo que la enmienda tiene que preservar.** El estándar prohíbe ORM porque
quiere una cosa: que el BFF no sea un segundo API de producto. La identidad
respeta ese principio desde el otro lado — no es dominio de seguros y no
puede vivir en otro lado. Por eso la excepción se escribe **acotada por
enumeración** (usuarios, cuentas, sesiones, tokens de verificación, rol) y no
por categoría: «persistencia de identidad» sin lista es la puerta por la que
en seis meses entra una tabla de preferencias, después una de favoritos, y el
estándar dejó de decir algo.

Dos consecuencias que la enmienda hace explícitas:

- **`lib/auth/` va separado de `lib/ai-service/`**, y no se importan entre
  sí. Una habla con Postgres vía Prisma, la otra con FastAPI. Mezclarlas es
  cómo una consulta de negocio termina saliendo de la base equivocada. El
  esquema en sí vive en `prisma/schema.prisma`, que es donde Prisma lo
  espera; `lib/auth/` queda para el cliente, el hashing y el rol.
- **La identidad va en su propia base**, en la misma instancia de Postgres
  que el corpus. Ver §1b.

## 1b. «Compartir la base» tiene tres niveles, y se eligió el primero

**Decisión:** misma **instancia** de Postgres, **base distinta**.

> **Enmendado el 2026-09-10, después de verificar el despliegue.** Lo que se
> implementó no es el nivel A sino uno más fuerte: la identidad quedó en **otra
> instancia** de Postgres, no en otra base de la misma. `AUTH_DATABASE_URL`
> apunta a la base `railway` de una instancia de Railway y el corpus vive en la
> base `railway` de **otra**: mismo proxy TCP de Railway, puertos distintos.
> (Los host:puerto reales no van acá: el repo es público y un endpoint de
> Postgres escrito en un `.md` es un blanco gratis. Están en `.env.local`, que
> no se commitea.) Confirmado consultando `pg_database` en la instancia de identidad:
> tiene `postgres` y `railway`, y esa `railway` contiene exactamente `User`,
> `Account`, `Session`, `VerificationToken` y `_prisma_migrations`, ninguna
> tabla del corpus.
>
> **La decisión se enmienda en vez de corregir el despliegue**, y la razón es
> que el objetivo se cumplió por una vía mejor. Todo lo que §1b quería —que un
> `pg_dump` del corpus no pueda traer contraseñas, que alembic no vea estas
> tablas, que restaurar el corpus no se lleve las cuentas— lo da una instancia
> aparte con más margen que una base aparte. Crear `dw-insu` ahora solo
> cambiaría un nombre: exigiría migrar las dos cuentas existentes, repuntar la
> variable en local y en Vercel y volver a sembrar el admin, sin ganar ninguna
> propiedad.
>
> **Lo que la enmienda sí cuesta**, y hay que decirlo: se pierde el ahorro que
> motivaba el nivel A. Son dos instancias que provisionar, pagar, respaldar y
> monitorear en lugar de una. Con el tamaño de esto —dos cuentas y cuatro
> tablas— es un costo teórico, pero es el argumento del cuadro de abajo
> yéndose, no un detalle.
>
> Entonces, con nombres reales, lo vigente es:
>
> ```
> Postgres A de Railway (:31812)      Postgres B de Railway (:37392)
> `-- railway  el corpus              `-- railway  la identidad
> ```
>
> El resto de esta sección se deja **tal como se escribió**: el análisis de
> por qué B y C cuestan más sigue siendo el que sostiene la decisión, y el
> nivel elegido de hecho es todavía más lejano a B que el que se había
> planeado. Lo único que ya no corresponde es el nombre `dw-insu` y el diagrama
> de una sola instancia.

Compartir no es binario, y la diferencia entre los niveles es lo que cuesta
cada uno:

| Nivel | Qué es | Costo |
|---|---|---|
| **A. Misma instancia, base aparte** | Un Postgres, dos bases | Casi nulo. Un `pg_dump` de una no trae la otra, y las credenciales son por base |
| **B. Misma base, schema aparte** | `auth.users` junto a `public.chunks` | Una connection string alcanza las dos, y alembic empieza a pelear |
| **C. Misma base, mismo schema** | Todo mezclado | Lo de B más colisiones de nombres |

**A** da el ahorro real que motiva la pregunta —una sola instancia que
provisionar, pagar, respaldar y monitorear— sin ninguno de los costos. Por
eso es la elegida.

Con nombres reales:

```
Postgres de Railway (una instancia)
|-- railway     el corpus: chunks, corpus_versions, agent_profiles,
|               conversation_sessions, checkpoints...
`-- dw-insu     la identidad: users, accounts, verification_tokens   <- nueva
```

`railway` es el nombre que ya tiene la base del corpus —el default de
Railway—, no uno elegido. `dw-insu` es la que hay que crear.

**Por qué B cuesta más de lo que parece**, y no es una hipótesis: este repo ya
lo vivió. `alembic/env.py` mantiene un `_FOREIGN_TABLES` con las cuatro tablas
del checkpointer de LangGraph, y explica por qué: «Sin este filtro,
autogenerate las ve "de más" y propone borrarlas […] Verificado: la primera
autogeneración después de agregar el checkpointer incluía esos cuatro
`drop_table`». Con las tablas de auth en la misma base pasaría exactamente lo
mismo: las crea el adapter desde la consola, alembic no las conoce, y el
primer `--autogenerate` propone tirarlas. La mitigación son tres líneas, pero
lo que no se va es que **dos herramientas de migración operen sobre la misma
base**, y que restaurar el corpus a un punto anterior se lleve puestas las
cuentas de usuario.

Con el nivel A nada de eso aplica: alembic no ve la base de identidad.

## 2. Estrategia de sesión: JWT, y no por gusto

**Decisión:** `session.strategy = "jwt"`, con el rol adentro del token.

No es una preferencia, y el modo en que falla es peor que un error.
Verificado en `@auth/core@0.41.3` instalado:

- `lib/init.js:74` decide el default así:
  `strategy: config.adapter ? "database" : "jwt"`. O sea que **configurar el
  adapter da vuelta el default a `database`**.
- `lib/actions/callback/index.js:227` en adelante: la rama de credenciales
  escribe **siempre** una cookie JWT —llama a `callbacks.jwt`, `jwt.encode` y
  setea la cookie— sin pasar nunca por el `createSession` del adapter.

Las dos cosas juntas dan el peor desenlace posible: con el default, el login
por contraseña **parece** funcionar —la cookie se setea, no hay excepción— y
después la lectura de sesión busca una fila en la tabla `sessions` que nunca
se escribió. El usuario queda deslogueado sin un solo error en los logs.

Por eso `session.strategy = "jwt"` va **explícito**, y por eso es la primera
línea de `auth.ts` que hay que revisar si algo del login se comporta raro.

Consecuencias que hay que aceptar con los ojos abiertos:

- **Revocar una sesión no es inmediato.** Un token firmado vale hasta que
  vence. Cambiarle el rol a alguien no lo degrada hasta que renueve. Para dos
  roles y una consola interna es tolerable; si algún día hace falta expulsar a
  alguien al instante, eso es otro change y probablemente otra estrategia.
- **El rol viaja en el token**, así que una página que decide por rol no
  consulta la base en cada request. A cambio, el token es más grande y hay
  que refrescarlo cuando el rol cambia.

`develop-web` tiene que **verificar esta restricción contra la versión
instalada** antes de comprometer el diseño. La compatibilidad de versiones ya
está resuelta (ver «lo que queda sin resolver»), pero que el proveedor de
credenciales siga atado a JWT es comportamiento del SDK, no metadata del
paquete, y en una beta eso se confirma leyendo la versión que se instaló.

## 3. Middleware para el gate, servidor para el rol

**Decisión:** `proxy.ts` responde «¿hay sesión?» y nada más. El rol se
verifica en el layout del grupo `(console)`, del lado del servidor.

**Es `proxy` y no `middleware`.** El convention `middleware` está deprecado en
Next 16 y renombrado a `proxy`; misma funcionalidad, cambian el nombre del
archivo y el del export. Escribir `middleware.ts` sería nacer sobre una API
deprecada.

Poner todo ahí es tentador porque es un solo lugar. Es también el error que la
documentación desaconseja, y con estas palabras: «Proxy is meant to be invoked
separately of your render code and in optimized cases deployed to your CDN
[…] you should not attempt relying on shared modules or globals». Corre en el
borde, lejos de los datos, y una comprobación que se saltea ahí no tiene
segunda línea. El patrón sano es **optimista en el borde, verdadero cerca de
los datos**.

De ahí el 403 explícito: un rol insuficiente recibe una pantalla que dice que
no alcanza, no un 404. Se renderiza a mano y **no** con el `forbidden()` que
Next 16 ya trae: esa API está marcada experimental y exige
`experimental.authInterrupts`. Este change ya se apoya en Auth.js beta y en un
adapter que no declara Prisma 7; un tercer flag experimental encima es riesgo
apilado para el mismo resultado visible. Devolver 404 para «ocultar» la existencia de `/models`
no detiene a nadie que ya sabe que existe —está en el repo público— y sí
confunde a un usuario legítimo al que le falta un permiso.

Y de ahí que `CONSOLE_MODULES` gane `roles`: sirve para no mostrar lo que no
se puede usar, **no** para autorizar. Si alguien borra el filtro de la nav,
la ruta tiene que seguir cerrada. Un test o una verificación explícita en el
checklist debería fijarlo.

## 4. Autoservicio con aprobación, y sin vinculación automática

**Decisión revisada por el dueño (2026-09-06).** La versión anterior de esta
sección decía «sin autoservicio»: un login de Google con un email desconocido
se rechazaba y las cuentas las creaba un administrador. Se reemplaza por:

> Cualquiera SHALL poder crear su propia cuenta, con email + contraseña o con
> Google. La cuenta nace con rol `usuario` y **desactivada**. Un
> administrador la habilita.

**Por qué cambia.** La decisión vieja resolvía el acceso y creaba un problema
peor en el alta: sin autoservicio, dar de alta a alguien significaba que un
administrador eligiera y tipeara la contraseña de otra persona. Sin pantalla
de cambio de contraseña —fuera de alcance— esa contraseña quedaba para
siempre, conocida por dos personas. Eso no es una molestia operativa: es una
credencial compartida.

**Por qué no autoservicio a secas.** El motivo original sigue en pie y no lo
deroga la comodidad. La consola se despliega con URL pública en Vercel, y un
rol `usuario` alcanza `/answer`: registro abierto sin más significa que
cualquiera con una cuenta de Google consulta la documentación funcional del
cliente y gasta tokens de LLM en cada pregunta. La aprobación conserva la
propiedad que importaba —**nadie entra sin que un administrador lo habilite**—
y tira la que estorbaba.

Encaja además con lo que el dueño pidió para la pantalla: si hay que poder
desactivar cuentas, la columna existe igual. «Nace desactivada» no agrega
esquema, usa el que ya hace falta.

**Sin verificación de email, la aprobación es la verificación.** Nada impide
registrarse con `alguien-mas@ejemplo.com`: no se manda mail de confirmación
—sigue fuera de alcance— así que la dirección es una afirmación, no un hecho.
Quien habilita tiene que reconocer a la persona, no a la dirección. Conviene
que la pantalla lo diga.

**Y por eso `allowDangerousEmailAccountLinking` sigue apagado**, ahora con un
ataque concreto y no con un principio. Con autoservicio y sin verificación de
email, vincular por dirección es esto: alguien registra `victima@gmail.com`
con una contraseña que elige; después la víctima entra con Google, Auth.js
une las dos cuentas por el email, y el primero —que sabe la contraseña— queda
adentro de la cuenta de la segunda. Es el pre-hijacking clásico, y lo
habilita exactamente esa opción. Apagada, el segundo método falla con
`OAuthAccountNotLinked` y hay que entrar por donde uno se registró; vincular
los dos métodos lo hace un administrador a mano.

## 5. Rol → pantalla

**Decisión propuesta**, la que menos supone:

| Rol | Pantallas |
|---|---|
| `usuario` | `/`, `/answer`, `/search`, `/documents` |
| `administrador` | las anteriores más `/agents`, `/agents/flow`, `/models`, `/corpus`, `/users` |

El corte no es «lectura vs escritura» sino **qué queda roto si se usa mal**.
`/documents` escribe, pero es una vista previa de chunking que
`app-routes.md` marca como «**No persiste**». `/corpus`, en cambio, dispara un
rebuild destructivo, y `/models` guarda credenciales de proveedores. Esos dos
son los que justifican el rol.

`/agents` y `/agents/flow` quedan del lado administrador porque editan la
persona, el modelo y los guardrails con los que responde el sintetizador:
cambian **cómo contesta el sistema a todos**, no solo a quien lo toca.

Es la decisión más fácil de discutir de todo el change, y la más barata de
cambiar: es una lista.

## 5b. Prisma v7, fijado exacto

**Decisión:** Prisma v7 como ORM, elegida por el dueño del repo. Con dos
condiciones que salieron de verificar el registro de npm y no de suponer.

**La versión se fija exacta, `7.10.0`.** El dist-tag `latest` de `prisma`
apunta hoy a `8.0.0-rc.13`, así que un `pnpm add prisma` sin versión no trae
la 7: trae un release candidate de la major siguiente. Es el mismo criterio
que ya se tomó con Auth.js —fijar en vez de rangear— pero acá el motivo es
más duro: no es que una beta pueda moverse, es que el default apunta a otro
lado.

**El adapter no declara la 7, pero tampoco la bloquea.**
`@auth/prisma-adapter@2.11.3` pide
`@prisma/client: >=2.26.0 || >=3 || >=4 || >=5 || >=6`. El primer término no
tiene techo, así que 7.x instala sin conflicto; pero la enumeración se
detiene en la 6, y la 7 cambió la superficie del cliente generado. «No está
prohibido» no es «está soportado». Por eso el smoke test del adapter es una
tarea temprana y explícita (1.2) y no algo que se descubre a mitad del
change.

Lo que Prisma 7 sí mejora para este caso es el arranque en frío: el cliente
dejó de depender del motor en Rust. Eso importa en funciones de Vercel, donde
cada invocación puede pagar el cold start.

## 6. Runner de tests, y hasta dónde

**Decisión:** un runner para `lib/auth/` y nada más. Sin suite de UI.

`bff-standards.md` §Tests ya dejó la regla escrita: «No agregar Jest "por las
dudas". Si el BFF crece hasta tener lógica que no sea relay, el proposal
justifica el runner». Hashear y verificar una contraseña, y resolver un rol a
partir de una sesión, son lógica que no es relay y que **no se puede cubrir
desde `ai-service/tests/`**, que es donde el estándar manda el resto del
contrato.

Lo que se testea: hash y verificación (incluido que una contraseña incorrecta
falle), y la resolución de rol (incluido el default). Lo que no: páginas,
formularios, ni el flujo de OAuth, que necesita el proveedor real y se
verifica en el browser.

## Lo que queda sin resolver

- **Compatibilidad Next 16 + Auth.js v5: verificada, pero la versión es
  beta.** `next-auth@beta` declara `next: ^14 || ^15 || ^16` y
  `react: ^18.2 || ^19`, así que la instalación no es el riesgo. El riesgo es
  que no existe una 5.0.0 estable: van 32 betas, y una beta puede mover una
  API sin aviso. Por eso la versión se fija exacta y actualizar el SDK es un
  change con su propia verificación.
- **Provisionar la segunda base.** Decidido: misma instancia de Railway, base
  aparte (§1b). Queda por hacer, no por decidir.
- **Pooling en serverless.** Los Route Handlers corren como funciones de
  Vercel (`bff-standards.md` §Despliegue). Una conexión directa por
  invocación agota el pool de Postgres bajo concurrencia. Con Prisma eso se
  resuelve con **dos URLs** —una pooled para el runtime y `directUrl` para
  las migraciones, que no pueden ir por un pooler— y `develop-web` tiene que
  dejar las dos configuradas. Es restricción de despliegue, no preferencia.
- **Qué pasa con las sesiones de conversación.** `conversation_sessions` vive
  en la base del servicio y hoy no tiene dueño. Atarlas a un usuario es
  natural una vez que hay usuarios, pero necesita que el servicio sepa quién
  pregunta — o sea, el change de autenticación de `ai-service`. Queda
  anotado, no resuelto.

## 7. El tenant NO entra acá, y el orden no se puede invertir

**Decisión:** este change no le pone tenant al usuario. Ni columna, ni
comportamiento.

Hoy `TENANT_ID` es un **setting del despliegue**: un despliegue sirve a un
cliente. Verificado — todos los caminos de lectura lo toman de ahí
(`app/api/search.py:99` y `:161`, `app/api/answer.py:67`), y el único lugar
donde un request lo menciona es `app/api/corpus.py:94`, donde
`confirm_tenant_id` es un **guard**: tiene que coincidir con el configurado,
no lo elige.

Que un usuario «tenga tenant» solo significa algo si el tenant pasa a
decidirse por request. Y ahí aparece la inversión que hay que ver antes de
construirla: si la consola le manda `tenant_id` a un servicio que no
autentica a nadie, cualquiera que alcance la URL pública de Railway lee el
corpus de cualquier cliente. **Hoy eso es imposible** — no porque haya un
control, sino porque el tenant está clavado en el entorno. Agregar
multi-tenancy sin autenticar el servicio no mejora el aislamiento: **crea una
fuga que hoy no existe.**

De ahí el orden, que no es preferencia:

```
1. add-console-authentication   <- este change
2. autenticar ai-service        <- el que falta (add-dynamic-providers 9.6)
3. tenant por usuario           <- recien aca el tenant deja de ser un env
```

Tampoco se agrega la columna `tenant_id` «por las dudas». `AGENTS.md` pide no
pre-construir capas vacías, y una columna que nadie lee es exactamente eso;
en una tabla de identidad con pocas filas, agregarla el día que haga falta es
una migración barata. Y hay un detalle que el paso 3 va a tener que
resolver y conviene anotar ahora: el índice único parcial garantiza **una
sola versión activa por cliente**, así que multi-tenant no es filtrar por
`tenant_id`, es manejar el ciclo de vida de varios corpus a la vez.

## 8. La pantalla de usuarios

**Decisión:** `/users`, dentro del grupo `(admin)`. Lista las cuentas,
habilita y deshabilita, cambia el rol y borra.

Que **solo un administrador pueda promover** no necesita una regla propia: la
pantalla vive donde vive el resto de la configuración y el layout de `(admin)`
la cierra igual que a `/models`. La regla se escribe en el spec de todos
modos, porque es lo que el dueño pidió explícitamente y porque un requirement
que depende de dónde está un archivo se rompe callado cuando alguien mueve el
archivo.

### Tres barandas, y por qué cada una

**Nadie cambia su propio rol.** No para prevenir un ataque —un administrador
que quiere hacerse daño ya puede— sino un accidente: la fila de uno mismo es
la que está más a mano en la lista. Como efecto colateral, promoverse solo
deja de ser posible incluso si mañana `/users` se abriera por error.

**El último administrador activo no se puede degradar, desactivar ni
borrar.** Sin esta baranda, un clic deja la consola sin nadie que pueda
configurarla, y la única salida es `pnpm seed:admin` desde una máquina con la
URL de la base. La condición se evalúa **en la misma transacción** que el
cambio: contarlos antes y escribir después es una condición de carrera, y con
dos administradores sacándose el rol a la vez el resultado es cero.

**Borrar es distinto de desactivar, y las dos existen.** Desactivar conserva
la fila: quién era, cuándo entró, qué cuentas de Google tenía vinculadas.
Borrar la elimina junto con sus `Account` en cascada. El dueño pidió las dos;
la que hay que ofrecer primero en la interfaz es desactivar, porque es la que
sirve el 90% de las veces y la única de las dos que se puede deshacer.

### El costo que esto le pasa al JWT, y hay que pagarlo

`auth.ts` mete el rol en el token firmado para no pegarle a la base en cada
request, y lo dejó anotado: cambiarle el rol a alguien no lo degrada hasta
que renueve. Con dos roles y sin altas ni bajas, eso era tolerable.

Deja de serlo acá. Desactivar una cuenta que sigue entrando hasta que venza
su token no es «desactivar», y borrar una cuenta cuyo token sigue resolviendo
es peor. Las tres operaciones que suma esta pantalla necesitan efecto
inmediato o no son lo que dicen ser.

Así que el layout de `(console)` pasa a leer la fila del usuario —una consulta
por render, por id, en una tabla de identidad con pocas filas— y a decidir con
eso: si no existe o está desactivada, se cierra la sesión. El rol también sale
de ahí, y el del token queda como lo que era, un cache. Es exactamente la
reversión de lo que dice el comentario de `callbacks.jwt`, y ese comentario
hay que actualizarlo en el mismo commit: un comentario que explica una
decisión que ya no rige es peor que no tener comentario.

### Qué NO entra

Cambiar la contraseña de otro, resetearla, o mandar una invitación por mail.
Lo primero es una credencial compartida —el problema que §4 acaba de sacarse
de encima— y lo segundo y lo tercero necesitan mandar correo, que sigue fuera
de alcance. Alguien que pierde su contraseña vuelve a entrar por Google, o un
administrador borra la cuenta y la persona se registra de nuevo.

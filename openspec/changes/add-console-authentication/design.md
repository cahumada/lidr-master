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

No es una preferencia: el proveedor de credenciales de Auth.js **solo**
funciona con JWT. Las sesiones en base requieren que el adapter cree la
sesión, y el flujo de credenciales no pasa por ahí. Pedir email + contraseña
y sesiones en base a la vez es pedir dos cosas incompatibles.

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

**Decisión:** `middleware.ts` responde «¿hay sesión?» y nada más. El rol se
verifica en el layout del grupo `(console)`, del lado del servidor.

Poner todo en el middleware es tentador porque es un solo lugar. Es también
el error que la documentación de Next desaconseja: el middleware corre en el
borde, lejos de los datos, y una comprobación que se saltea ahí no tiene
segunda línea. El patrón sano es **optimista en el borde, verdadero cerca de
los datos**.

De ahí el 403 explícito: un rol insuficiente recibe una pantalla que dice que
no alcanza, no un 404. Devolver 404 para «ocultar» la existencia de `/models`
no detiene a nadie que ya sabe que existe —está en el repo público— y sí
confunde a un usuario legítimo al que le falta un permiso.

Y de ahí que `CONSOLE_MODULES` gane `roles`: sirve para no mostrar lo que no
se puede usar, **no** para autorizar. Si alguien borra el filtro de la nav,
la ruta tiene que seguir cerrada. Un test o una verificación explícita en el
checklist debería fijarlo.

## 4. Sin autoservicio y sin vinculación automática

**Decisión:** un login de Google con un email que no está en la base se
**rechaza**. No se crea la cuenta sola. Y una cuenta de Google no se vincula
sola a una cuenta local con el mismo email.

Autoprovisionar con Google significa que cualquiera con cuenta de Google
entra. Restringir por dominio parece la solución, pero el dominio de un mail
no es una autorización: es un dato que el proveedor verificó para otra cosa.
En una consola que edita credenciales de proveedores y dispara rebuilds
destructivos, la lista blanca explícita cuesta menos que el primer incidente.

Sobre la vinculación: Auth.js tiene una opción para permitirla y se llama
`allowDangerousEmailAccountLinking`. El nombre es la documentación. Sin
verificación de email propia —fuera de alcance— vincular por dirección es
delegar la identidad en que el proveedor la verificó. Si alguien necesita los
dos métodos, un administrador vincula a mano.

Consecuencia práctica: **el primer administrador se siembra**, con un script
que corre una persona con acceso a la base. No hay un «primer login se
autoproclama admin», que es como se abre un agujero el día que la URL se
filtra.

## 5. Rol → pantalla

**Decisión propuesta**, la que menos supone:

| Rol | Pantallas |
|---|---|
| `usuario` | `/`, `/answer`, `/search`, `/documents` |
| `administrador` | las anteriores más `/agents`, `/agents/flow`, `/models`, `/corpus` |

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

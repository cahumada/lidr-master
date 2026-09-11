# web-console Delta Specification

## ADDED Requirements

### Requirement: La consola exige identificarse

Toda página de la consola SHALL requerir una sesión. Un visitante sin sesión
que pide una página protegida SHALL ser redirigido a `/login`, y después de
autenticarse SHALL aterrizar en el destino que pidió y no en la portada.

La autenticación SHALL ofrecer dos métodos: Google y email + contraseña. La
contraseña SHALL guardarse hasheada y NUNCA salir de la base ni aparecer en
un log. Un intento fallido SHALL responder sin decir si lo que falló fue el
email o la contraseña.

#### Scenario: sin sesión

- **WHEN** alguien sin sesión pide `/answer`
- **THEN** la consola redirige a `/login`
- **AND** después de autenticarse aterriza en `/answer`

#### Scenario: login con contraseña incorrecta

- **WHEN** alguien envía un email conocido con la contraseña equivocada
- **THEN** el login falla
- **AND** el mensaje no distingue entre email inexistente y contraseña
  incorrecta

#### Scenario: la sesión activa no vuelve al login

- **WHEN** alguien con sesión pide `/login`
- **THEN** la consola lo lleva adentro en vez de mostrar el formulario

#### Scenario: cerrar sesión borra las cookies

- **WHEN** alguien cierra sesión
- **THEN** la consola vence las cookies de Auth.js (sesión, csrf, callback,
  pkce, state) y las demás cookies de este origen
- **AND** lo manda a `/login` sin sesión residual

### Requirement: Dos roles, y el rol decide qué se puede usar

La consola SHALL distinguir `usuario` de `administrador`. Una cuenta nueva
SHALL nacer como `usuario`, con el default declarado en la base y no solo en
el código.

Las pantallas que **escriben configuración o destruyen datos** —`/agents`,
`/agents/flow`, `/models`, `/corpus`, `/users`— SHALL exigir `administrador`.
El resto —`/`, `/answer`, `/search`, `/documents`— SHALL estar disponible
para cualquier sesión activa.

Un rol insuficiente SHALL recibir una **pantalla de 403**, no un 404 ni una
redirección silenciosa: ocultar que la pantalla existe no detiene a quien ya
sabe que existe, y confunde a quien legítimamente necesita el permiso.

**El status HTTP de esa respuesta es 200, y esto lo declara a propósito.** Un
layout de Next no puede fijar el status sin `forbidden()`, que exige el flag
`experimental.authInterrupts`; el change que introdujo esto ya se apoyaba en
Auth.js beta y en un adapter que no declara Prisma 7, y un tercer flag
experimental encima es riesgo apilado para el mismo resultado visible. Mover el
chequeo al `proxy` para poder devolver el status es peor: el borde lee la cookie
sin verificar su firma, así que un chequeo de rol ahí falla **abierto**.

O sea: una persona ve 403 y un cliente programático ve 200. Se acepta porque
estas rutas son pantallas de la consola y no API — no hay cliente programático
de ellas—. Si alguna vez lo hay, esto es el requirement que hay que reabrir, y
la salida es el flag.

#### Scenario: usuario en una pantalla de administrador

- **WHEN** una sesión con rol `usuario` pide `/models`
- **THEN** la consola muestra la pantalla de 403, que explica qué pasó
- **AND** NO responde 404 ni redirige en silencio
- **AND** el status HTTP es 200, por la razón declarada arriba

#### Scenario: administrador en la misma pantalla

- **WHEN** una sesión con rol `administrador` pide `/models`
- **THEN** la pantalla carga normalmente

#### Scenario: una cuenta nueva no nace administradora

- **WHEN** se crea una cuenta por cualquiera de los dos métodos
- **THEN** su rol es `usuario`

### Requirement: Cualquiera puede registrarse, nadie entra sin aprobación

La consola SHALL permitir que una persona cree su propia cuenta, con email +
contraseña o con Google. La cuenta SHALL nacer con rol `usuario` y
**desactivada**, y una cuenta desactivada NO SHALL poder iniciar sesión por
ningún método.

Habilitarla SHALL requerir un administrador. La consola NO SHALL enviar
correo de verificación ni de invitación, de modo que la dirección declarada
al registrarse es una afirmación sin comprobar: quien habilita SHALL estar
reconociendo a la persona y no a la dirección, y la pantalla SHALL decirlo.

Una cuenta de Google NO SHALL vincularse automáticamente a una cuenta local
con el mismo email. Sin verificación de email, vincular por dirección
permitiría registrar el email de otro con una contraseña propia y quedar
dentro de su cuenta cuando esa persona entre con Google.

#### Scenario: alguien se registra

- **WHEN** alguien completa el registro con email y contraseña
- **THEN** se crea su cuenta con rol `usuario` y desactivada
- **AND** el mensaje le dice que un administrador tiene que habilitarla

#### Scenario: Google pide elegir la cuenta

- **WHEN** alguien entra o se registra con Google
- **THEN** Google muestra el selector de cuentas
- **AND** no reutiliza en silencio la sesión de Gmail que ya estaba abierta

#### Scenario: la cuenta recién creada intenta entrar

- **WHEN** esa persona intenta iniciar sesión antes de ser habilitada
- **THEN** el login falla
- **AND** el mensaje distingue «falta habilitación» de «credenciales
  incorrectas», porque son dos problemas con dos soluciones distintas

#### Scenario: Google con un email que ya existe como cuenta local

- **WHEN** alguien registrado con email y contraseña intenta entrar con
  Google usando la misma dirección
- **THEN** la consola NO vincula las dos cuentas sola
- **AND** el mensaje indica entrar por el método con el que se registró

#### Scenario: un administrador vincula Google a su propia cuenta

- **WHEN** un administrador con sesión por contraseña elige vincular Google
  desde `/users`
- **THEN** Auth.js asocia el `Account` de Google a esa fila
- **AND** después puede entrar con cualquiera de los dos métodos

### Requirement: Un administrador administra las cuentas

La consola SHALL ofrecer `/users`, restringida a `administrador`, que lista
las cuentas con su email, nombre, rol, estado y método de login.

Desde ahí un administrador SHALL poder habilitar y deshabilitar una cuenta,
cambiar su rol y borrarla. **Cambiar el rol de `usuario` a `administrador`
SHALL requerir una sesión con rol `administrador`**, y esa promoción SHALL
ser el único camino por el que alguien llega a ese rol dentro de la consola.

Ninguna sesión SHALL poder cambiar su propio rol.

La consola NO SHALL permitir degradar, deshabilitar ni borrar al último
administrador habilitado, y esa comprobación SHALL resolverse en la misma
transacción que el cambio.

Deshabilitar, degradar y borrar SHALL tener efecto en la sesión que ya está
abierta, sin esperar a que venza su token.

La consola NO SHALL ofrecer cambiar ni resetear la contraseña de otra
persona.

#### Scenario: promover a alguien

- **WHEN** un administrador cambia el rol de una cuenta `usuario` a
  `administrador`
- **THEN** el cambio se guarda
- **AND** esa cuenta alcanza las pantallas de administración

#### Scenario: promoverse a sí mismo

- **WHEN** una sesión intenta cambiar el rol de su propia cuenta
- **THEN** la consola lo rechaza

#### Scenario: el último administrador

- **WHEN** un administrador intenta degradarse, deshabilitarse o borrarse
  siendo el último habilitado
- **THEN** la consola lo rechaza y explica que dejaría la consola sin
  administración

#### Scenario: deshabilitar a alguien que está adentro

- **WHEN** un administrador deshabilita una cuenta con sesión abierta
- **THEN** esa sesión deja de alcanzar las páginas protegidas en su siguiente
  request, sin esperar a que venza el token

### Requirement: La autorización vive en el servidor, no en la navegación

`CONSOLE_MODULES` SHALL declarar qué roles ven cada ítem, y el sidebar y la
portada SHALL filtrar por eso. Ese filtro es presentación: NO es el control
de acceso.

La ruta SHALL protegerse del lado del servidor, de forma que desactivar el
filtro de la navegación no habilite ninguna pantalla. El `proxy` —el
convention que en Next 16 reemplaza a `middleware`— SHALL resolver únicamente
si hay sesión; el rol SHALL verificarse cerca de los datos, en el layout del
grupo protegido.

#### Scenario: la nav oculta lo que el rol no puede usar

- **WHEN** una sesión con rol `usuario` abre la consola
- **THEN** el sidebar y la portada no listan las pantallas de administrador

#### Scenario: saltear la nav no alcanza

- **WHEN** una sesión con rol `usuario` navega a mano a una pantalla de
  administrador, sin pasar por el sidebar
- **THEN** recibe la pantalla de 403 igual — el filtro de la nav no autoriza

### Requirement: El login de la consola NO es lo que protege al servicio

La consola SHALL autenticar a quien la usa, y eso NO SHALL presentarse como
protección de `ai-service`: son dos puertas distintas y se cierran por separado.

**Reformulado el 2026-09-10.** Este requirement decía «`ai-service`, que no
tiene autenticación propia y se despliega con URL pública», y eso dejó de ser
cierto: `add-service-authentication` cerró el servicio con un token compartido
que el cliente base agrega en cada llamada, y con `APP_ENV=production` el
servicio no arranca sin el suyo. Promoverlo tal cual habría metido una
afirmación falsa en `openspec/specs/`.

Lo que sí sigue en pie, y es lo que este requirement existe para que nadie
deduzca al revés: **el login de personas no es lo que cierra el servicio, y el
token del servicio no identifica personas.** Quien tenga el token alcanza
`ai-service` sin pasar por la consola y sin ser nadie en particular; el ledger
de uso atribuye la llamada al portador —el BFF— y no a quien preguntó.

El estándar del BFF SHALL distinguir las dos, para que un lector futuro no
deduzca de la existencia del login que los endpoints están cerrados, ni del
token que hay identidad de usuario en el servicio.

#### Scenario: el estándar distingue las dos puertas

- **WHEN** alguien lee la sección de seguridad del estándar del BFF
- **THEN** encuentra la autenticación de personas y la del servicio como dos
  bullets separados, cada uno con su mecanismo
- **AND** encuentra dicho que cerrar el servicio no le da identidad de usuario

## MODIFIED Requirements

<!--
Corregido al archivar (2026-09-11). El texto que este delta traía para este
requirement era el ANTERIOR a `add-answer-history-console`, que lo superseded el
2026-09-10: decía que empezar un hilo nuevo descarta la sesión en el servicio, y
hoy la spec dice lo contrario —descartar es una acción explícita sobre la lista—.
Promoverlo tal cual habría hecho retroceder la spec. Se conserva el texto vigente
y se le suma lo único que este change aporta: que la sesión de conversación no es
la sesión de identidad, y su escenario.
-->

### Requirement: La respuesta es un chat de sesión
La pantalla de respuesta SHALL presentar un hilo: cada envío appendea el
mensaje del usuario y el turno del asistente, sin pisar los turnos
anteriores de la misma sesión. El compositor SHALL quedar al pie. Cada turno
SHALL seguir siendo una corrida agentica independiente
(`POST /answer/agentic/start` + sondeo de progreso).

El hilo SHALL estar respaldado por una sesión del servicio: la pantalla pide
un `session_id` a `POST /answer/session` en la primera pregunta (perezoso) y
lo manda en cada turno. La pantalla SHALL listar las conversaciones no vacías
del tenant (`GET /api/answer/sessions`) y SHALL reabrir una al elegirla
(`GET /api/answer/session/{id}`), armando el hilo desde `history` y los
anchors. La URL SHALL llevar `?session=<id>` cuando hay un hilo activo, para
que una recarga restaure el mismo transcript.

Empezar un hilo nuevo SHALL limpiar el estado local y el query param, y
SHALL NOT descartar la sesión anterior en el servicio. Descartar SHALL ser
una acción explícita sobre una fila de la lista (`DELETE`). Renombrar SHALL
usar `PATCH` y SHALL mostrar un 422 en vez de tragárselo.

Cuando el servicio resuelve una pregunta referencial, la pantalla SHALL
mostrar la pregunta resuelta junto a la escrita, y SHALL mostrar los anchors
vigentes con la opción de quitarlos.

Un turno reabierto SHALL mostrar las citas que el historial trajo. Si el
snapshot no lleva `text` del chunk, la pantalla SHALL mostrar documento y
sección y SHALL NOT inventar el texto.

Si el listado no está disponible, la pantalla SHALL degradar a lista vacía
más un aviso y SHALL seguir dejando preguntar.
Esa sesión de conversación NO es la sesión de identidad: la primera recuerda de
qué se habló, la segunda dice quién habla. La pantalla SHALL requerir una sesión
de consola como cualquier otra, y el servicio no sabe quién pregunta: autentica
a su llamador con un token compartido, y un token no es una persona.

#### Scenario: segunda pregunta en la misma sesión
- **WHEN** el usuario envía una pregunta después de haber recibido una
  respuesta en la misma carga de la página
- **THEN** el hilo muestra ambos turnos
- **AND** el segundo turno se envía con el mismo `session_id` que el primero
- **AND** el compositor queda al pie, no arriba del hilo

#### Scenario: pregunta de seguimiento resuelta
- **WHEN** el servicio devuelve una `resolved_question` distinta de la
  escrita
- **THEN** el turno muestra las dos
- **AND** queda claro cuál se buscó contra el corpus

#### Scenario: hilo nuevo
- **WHEN** el usuario pide un chat nuevo
- **THEN** el hilo local queda vacío
- **AND** la sesión anterior sigue en la lista
- **AND** el turno siguiente usa un `session_id` nuevo

#### Scenario: reabrir después de recargar
- **WHEN** el operador tiene un hilo activo en `/answer?session=<id>` y
  recarga
- **THEN** la pantalla vuelve a pedir ese id
- **AND** el hilo muestra los turnos de `history`, no un compositor vacío

#### Scenario: citas de un turno reabierto
- **WHEN** un `HistoryTurn` trae snapshots sin `text`
- **THEN** cada cita muestra `document_id` y, si vienen, título y sección
- **AND** no se pinta un recuadro de chunk vacío

#### Scenario: borrar es explícito
- **WHEN** el operador borra una fila de la lista
- **THEN** la consola llama `DELETE` a esa sesión
- **AND** si era la activa, el compositor queda vacío

#### Scenario: anchors visibles
- **WHEN** un turno aplicó un filtro fijado en un turno anterior
- **THEN** la pantalla muestra ese filtro como vigente
- **AND** ofrece quitarlo

#### Scenario: gate humano en un turno
- **WHEN** una corrida responde 202 con `status=awaiting_human_review`
- **THEN** ese turno muestra las razones y las acciones de aprobar/rechazar
- **AND** los turnos anteriores del hilo siguen visibles

#### Scenario: sin sesión de consola no hay chat
- **WHEN** alguien sin sesión de consola pide la pantalla de respuesta
- **THEN** es redirigido a `/login`
- **AND** no se crea ninguna sesión de conversación en el servicio

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

### Requirement: Dos roles, y el rol decide qué se puede usar

La consola SHALL distinguir `usuario` de `administrador`. Una cuenta nueva
SHALL nacer como `usuario`, con el default declarado en la base y no solo en
el código.

Las pantallas que **escriben configuración o destruyen datos** —`/agents`,
`/agents/flow`, `/models`, `/corpus`— SHALL exigir `administrador`. El resto
—`/`, `/answer`, `/search`, `/documents`— SHALL estar disponible para
cualquier sesión.

Un rol insuficiente SHALL recibir **403**, no 404 ni una redirección
silenciosa: ocultar que la pantalla existe no detiene a quien ya sabe que
existe, y confunde a quien legítimamente necesita el permiso.

#### Scenario: usuario en una pantalla de administrador

- **WHEN** una sesión con rol `usuario` pide `/models`
- **THEN** la consola responde 403 con una pantalla que lo explica
- **AND** NO responde 404

#### Scenario: administrador en la misma pantalla

- **WHEN** una sesión con rol `administrador` pide `/models`
- **THEN** la pantalla carga normalmente

#### Scenario: una cuenta nueva no nace administradora

- **WHEN** se crea una cuenta por cualquiera de los dos métodos
- **THEN** su rol es `usuario`

### Requirement: La autorización vive en el servidor, no en la navegación

`CONSOLE_MODULES` SHALL declarar qué roles ven cada ítem, y el sidebar y la
portada SHALL filtrar por eso. Ese filtro es presentación: NO es el control
de acceso.

La ruta SHALL protegerse del lado del servidor, de forma que desactivar el
filtro de la navegación no habilite ninguna pantalla. El middleware SHALL
resolver únicamente si hay sesión; el rol SHALL verificarse cerca de los
datos, en el layout del grupo protegido.

#### Scenario: la nav oculta lo que el rol no puede usar

- **WHEN** una sesión con rol `usuario` abre la consola
- **THEN** el sidebar y la portada no listan las pantallas de administrador

#### Scenario: saltear la nav no alcanza

- **WHEN** una sesión con rol `usuario` navega a mano a una pantalla de
  administrador, sin pasar por el sidebar
- **THEN** recibe 403 igual

### Requirement: El login de la consola NO protege al servicio

La consola SHALL autenticar a quien la usa, y eso NO SHALL presentarse como
protección de `ai-service`, que no tiene autenticación propia y se despliega
con URL pública. Quien conozca esa URL sigue alcanzando el servicio sin pasar
por la consola.

Esta limitación SHALL quedar escrita en el estándar del BFF, para que un
lector futuro no deduzca de la existencia del login que los endpoints están
cerrados.

#### Scenario: el estándar dice qué queda abierto

- **WHEN** alguien lee la sección de seguridad del estándar del BFF
- **THEN** encuentra dicho que autenticar la consola no autentica el servicio
- **AND** que hacerlo es un change aparte

## MODIFIED Requirements

### Requirement: La respuesta es un chat de sesión
La pantalla de respuesta SHALL presentar un hilo: cada envío appendea el
mensaje del usuario y el turno del asistente, sin pisar los turnos
anteriores de la misma sesión. El compositor SHALL quedar al pie. Cada turno
SHALL seguir siendo una corrida agentica independiente
(`POST /answer/agentic/start` + sondeo de progreso).

El hilo SHALL estar respaldado por una sesión del servicio: la pantalla pide
un `session_id` a `POST /answer/session` y lo manda en cada turno, así que
la conversación deja de vivir solo en el estado del browser. Empezar un hilo
nuevo SHALL descartar esa sesión en el servicio (`DELETE`) además de limpiar
el estado local — a diferencia del comportamiento anterior, ahora sí llama
al servicio, porque dejar la sesión viva sería dejar memoria colgada de un
hilo que el usuario dio por terminado.

Cuando el servicio resuelve una pregunta referencial, la pantalla SHALL
mostrar la pregunta resuelta junto a la escrita, y SHALL mostrar los anchors
vigentes con la opción de quitarlos.

Esa sesión de conversación NO es la sesión de identidad: la primera recuerda
de qué se habló, la segunda dice quién habla. La pantalla SHALL requerir una
sesión de consola como cualquier otra, y hoy el servicio no sabe quién
pregunta.

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
- **AND** la sesión anterior se descarta en el servicio
- **AND** el turno siguiente usa un `session_id` nuevo

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

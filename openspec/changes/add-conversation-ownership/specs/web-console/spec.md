# web-console Delta Specification

## MODIFIED Requirements

### Requirement: La respuesta es un chat de sesión
La pantalla de respuesta SHALL presentar un hilo: cada envío appendea el
mensaje del usuario y el turno del asistente, sin pisar los turnos
anteriores de la misma sesión. El compositor SHALL quedar al pie. Cada turno
SHALL seguir siendo una corrida agentica independiente
(`POST /answer/agentic/start` + sondeo de progreso). Un 502 o un fallo de
red en un sondeo SHALL reintentarse; el turno solo SHALL marcarse fallido
cuando ese fallo persiste más de tres minutos desde el envío.

El hilo SHALL estar respaldado por una sesión del servicio: la pantalla pide
un `session_id` a `POST /answer/session` en la primera pregunta (perezoso) y
lo manda en cada turno. La pantalla SHALL listar las conversaciones no vacías
**de quien está mirando** (`GET /api/answer/sessions`) y SHALL reabrir una al elegirla
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

#### Scenario: un 502 transitorio del sondeo no aborta el turno
- **WHEN** un poll de `/progress` responde 502 mientras el grafo sigue
  corriendo y el turno lleva menos de tres minutos
- **THEN** la pantalla reintenta el sondeo
- **AND** no marca el turno como fallido

Una conversación SHALL ser de la persona que la empezó, y de nadie más. El BFF
SHALL mandarle al servicio la identidad de la sesión de Auth.js, y el servicio
SHALL filtrar por ella. Un rol de administración SHALL NOT ampliar lo que se ve:
auditar una respuesta es `prompt-inspection`, que deja rastro; leer el historial
de otra persona no es lo mismo y no tiene pantalla.

Reabrir por URL SHALL respetar lo mismo que la lista: un `?session=<id>` ajeno
SHALL comportarse como uno inexistente, y la pantalla SHALL NOT mostrar su
transcript.

#### Scenario: La lista es de quien mira
- **WHEN** dos personas distintas conversaron en el mismo despliegue
- **THEN** cada una lista solo las conversaciones que empezó ella
- **AND** la lista de una no cambia cuando la otra conversa

#### Scenario: Un id ajeno pegado en la URL
- **WHEN** alguien abre `/answer?session=<id>` de una conversación ajena
- **THEN** la pantalla no arma el hilo con ese transcript
- **AND** se comporta como con un id que no existe

#### Scenario: El administrador tampoco
- **WHEN** quien mira tiene rol `administrador`
- **THEN** la lista sigue siendo la de sus propias conversaciones

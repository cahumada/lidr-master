# web-console Delta Specification

## MODIFIED Requirements

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

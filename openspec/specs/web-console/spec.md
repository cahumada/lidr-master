# web-console Specification

## Purpose

La consola de operación del servicio: las pantallas que un analista funcional
usa para buscar en el corpus, preguntarle al grafo de respuesta, previsualizar
una ingesta, reconstruir el corpus y configurar agentes y modelos — más la capa
que las conecta con el servicio IA.

Implementado en `business-backend/`: `app/(console)/` las pantallas, `app/api/`
los Route Handlers, `lib/ai-service/` el único cliente HTTP contra el servicio.

Promovido de: `add-web-console`, `add-answer-console`, `add-flow-worked-example`,
`add-model-catalog-filter`, `add-named-agent-profiles-and-flow`,
`expose-agent-prompt-inspector`, `reorganize-console-modules`,
`add-conversation-memory`, `fix-silent-answer-truncation`,
`render-answer-markdown`, `add-answer-history-console`, `add-llm-usage-console`,
`improve-agents-console-layout`, `add-window-status-console`.

**Un hueco declarado.** El aislamiento de despliegue está especificado solo en
su mitad implementada: CI filtra por rutas (`dorny/paths-filter` en
`.github/workflows/ci.yml`), pero **el filtrado del lado de las plataformas
—Railway y Vercel— no está configurado**. `add-web-console` se cerró sin esa
configuración (decisión del dueño del repo, 2026-09-10), así que la spec afirma
lo que CI hace y no lo que las plataformas todavía no hacen. Hasta que se
configure, un commit que toca un solo proyecto puede producir un deploy del otro.

**Y una cosa quedó afuera**, porque una spec afirma lo que el código hace hoy:

- Los siete requirements de **identidad y roles** de
  `add-console-authentication`, que tiene 23 tasks abiertas. El único punto
  donde el documento actual roza el tema es el gate de `/usage` al rol
  `administrador`, que la pantalla ya aplica.

## Requirements

### Requirement: El browser nunca llama al servicio IA directo
Toda llamada al servicio IA SHALL originarse en el servidor de
`business-backend/` (Route Handlers), usando una variable de entorno privada
para la URL. Ningún componente de cliente SHALL leer esa URL, y ninguna
respuesta al browser SHALL contenerla.

#### Scenario: el browser solo ve el origen de la app web
- **WHEN** un usuario ejecuta una búsqueda desde el browser
- **THEN** la request de red del browser tiene como destino una ruta de
  `business-backend/` (p. ej. `/api/search`)
- **AND** ni el bundle de cliente ni ninguna respuesta contienen la URL del
  servicio IA

### Requirement: Una sola capa habla HTTP con el servicio IA

El acceso HTTP al servicio IA SHALL estar confinado a `lib/ai-service/`: un
cliente base más un cliente por contexto (`search`, `documents`, `corpus`).
Ninguna pantalla ni Route Handler SHALL hacer `fetch` al servicio por su
cuenta, y los contextos NO SHALL importarse entre sí.

Ese cliente base SHALL adjuntar el token de servicio en cada request, en el
único lugar donde se hace `fetch` contra el servicio. La variable SHALL vivir
del lado del servidor y **SHALL NOT** llevar el prefijo `NEXT_PUBLIC_`: ese
prefijo es exactamente el mecanismo que la expondría al browser. El módulo ya es
`server-only`, así que la garantía es estructural y no una convención — la misma
razón por la que `AI_SERVICE_URL` vive ahí.

Cuando la variable no está configurada, el cliente SHALL NOT mandar el header ni
inventar un valor: el servicio puede estar abierto a propósito en desarrollo.

#### Scenario: agregar una llamada nueva
- **WHEN** una pantalla necesita un endpoint del servicio IA que todavía no se
  consume
- **THEN** el método nuevo se agrega al cliente del contexto que corresponde
- **AND** la pantalla lo consume a través de ese cliente, nunca con un `fetch`
  propio

#### Scenario: el token viaja en toda llamada
- **WHEN** cualquier cliente de contexto llama al servicio
- **THEN** la request lleva el token, porque lo agrega el cliente base
- **AND** ninguna pantalla ni Route Handler lo maneja

#### Scenario: el token no puede llegar al browser
- **WHEN** se inspecciona el bundle de cliente y cualquier respuesta al browser
- **THEN** el token no aparece en ninguno de los dos

### Requirement: La app web nunca llama a un proveedor de modelos
`business-backend/` SHALL obtener toda capacidad de IA del servicio IA. NO
SHALL contener credenciales de ningún proveedor de modelos, ni siquiera del
lado del servidor, ni llamar a un proveedor directamente.

#### Scenario: una funcionalidad nueva necesita un modelo
- **WHEN** una pantalla necesita algo que requiere una llamada a un LLM
- **THEN** esa llamada la hace el servicio IA detrás de un endpoint propio
- **AND** la app web solo consume ese endpoint

### Requirement: Las vistas renderizan objetos tipados
Las respuestas del servicio IA SHALL estar tipadas en TypeScript espejando los
schemas Pydantic del servicio. Ninguna pantalla SHALL renderizar JSON crudo ni
acceder a campos no declarados en esos tipos.

#### Scenario: el servicio agrega un campo
- **WHEN** el servicio IA agrega un campo a una respuesta
- **THEN** el tipo de `lib/ai-service/types.ts` se actualiza antes de que
  ninguna pantalla lo use

### Requirement: La consola se ve en claro y en oscuro, sin flash
Toda pantalla SHALL renderizarse legible en tema claro y en tema oscuro, con un
único juego de tokens de color: ninguna pantalla SHALL fijar un color literal
que no salga de esos tokens. Cuando el usuario no eligió tema, la consola SHALL
seguir la preferencia del sistema (`prefers-color-scheme`); cuando eligió, esa
elección SHALL persistir entre recargas y ganarle al sistema. El tema vigente
SHALL quedar aplicado antes del primer pintado, no después de hidratar.

#### Scenario: primera visita con el sistema en oscuro
- **WHEN** un usuario que nunca eligió tema abre la consola con su sistema
  operativo en modo oscuro
- **THEN** la primera pintura de la página ya es oscura
- **AND** no se ve un fondo claro intermedio

#### Scenario: la elección sobrevive la recarga
- **WHEN** el usuario cambia el tema con el conmutador y recarga la página
- **THEN** la página vuelve con el tema que eligió
- **AND** ese tema se mantiene aunque el sistema operativo pida el contrario

### Requirement: Los errores del servicio se muestran con su significado
La app web SHALL distinguir los errores documentados del servicio y mostrarlos
con su significado, nunca como una falla genérica ni como una traza cruda. Un
409 de `POST /corpus/rebuild` SHALL presentarse como "hay una reconstrucción en
curso" con referencia al job existente.

#### Scenario: ya hay un job corriendo
- **WHEN** el usuario pide una reconstrucción y el servicio responde 409
- **THEN** la pantalla informa que ya hay una reconstrucción en curso y enlaza
  al job que la está ejecutando

#### Scenario: el servicio IA no responde
- **WHEN** el servicio IA está caído o devuelve 5xx
- **THEN** la pantalla muestra un mensaje que dice qué falló
- **AND** no expone una traza ni el detalle interno de la respuesta

### Requirement: CI DEBE correr los checks de un proyecto solo cuando cambian sus rutas
El monorepo tiene dos proyectos con toolchains distintos. Correr la suite de
Python porque cambió un `.tsx` gasta tiempo y produce rojos que no dicen nada
sobre el commit.

El filtrado de plataformas —que Vercel y Railway desplieguen solo por cambios en
sus rutas— es configuración de cada dashboard y **no está hecha**; ver el hueco
declarado arriba.

#### Scenario: cambio solo en la app web
- **WHEN** un commit a `main` toca únicamente archivos bajo `business-backend/`
- **THEN** el job de CI del servicio IA no se ejecuta

#### Scenario: cambio solo en el servicio IA
- **WHEN** un commit a `main` toca únicamente archivos bajo `ai-service/`
- **THEN** el job de CI de la app web no se ejecuta

### Requirement: La navegación agrupa las pantallas en tres módulos
La consola SHALL exponer la navegación en tres módulos: **Respuesta** (chat),
**RAG** (búsqueda, ingesta, corpus) y **Configuración** (tipos de agentes,
modelos). El destino activo SHALL distinguirse del resto. En viewport estrecho
la navegación SHALL poder abrirse y cerrarse sin perder el contenido.

#### Scenario: un operador abre la consola
- **WHEN** el usuario carga cualquier pantalla
- **THEN** ve los tres módulos con sus pantallas adentro
- **AND** el link de la pantalla actual queda marcado como activo

#### Scenario: viewport estrecho
- **WHEN** el usuario abre la consola en un ancho de móvil
- **THEN** la navegación no tapa el contenido hasta que la abre
- **AND** puede llegar a cada pantalla de los tres módulos

### Requirement: Configuración parte agentes y modelos
La consola SHALL servir tipos de agentes en `/agents` y proveedores/modelos
en `/models`. Ninguna de las dos pantallas SHALL mezclar el formulario del
otro contexto.

#### Scenario: configurar un agente
- **WHEN** el usuario entra a Configuración → Agentes
- **THEN** ve los agentes configurables y los deterministas
- **AND** no ve el formulario de credenciales ni el catálogo de modelos
      del proveedor

#### Scenario: cargar un modelo
- **WHEN** el usuario entra a Configuración → Modelos
- **THEN** ve proveedores, credenciales write-only y el catálogo de modelos
- **AND** no ve el formulario de persona de un agente

### Requirement: La pantalla de búsqueda expone la procedencia de cada resultado
La pantalla SHALL llamar a `GET /search` y renderizar, por cada resultado, su
`document_id`, `document_title`, `section`, `score` y las ramas (`branches`)
que lo encontraron. Cuando la descomposición está activa, SHALL mostrar las
`sub_queries` devueltas.

#### Scenario: resultado con procedencia completa
- **WHEN** una búsqueda devuelve al menos un resultado
- **THEN** cada resultado muestra su documento de origen, su sección y qué
  rama(s) de recuperación lo aportaron
- **AND** ningún resultado se muestra sin esa procedencia

#### Scenario: consulta compuesta con `split` activo
- **WHEN** el usuario deja activada la descomposición (default del endpoint)
- **THEN** la pantalla muestra las sub-preguntas en las que se dividió la
  consulta, tal como vienen en `SearchResponse.sub_queries`

### Requirement: Los filtros de módulo y tipo de ventana son de selección múltiple
La pantalla de búsqueda SHALL ofrecer `Módulo` y `Tipo de ventana` como
listados de selección múltiple, poblados desde `GET /api/search/facets` — no
desde una lista escrita a mano en la pantalla. `Módulo` SHALL tener "Todos"
seleccionado por default; `Tipo de ventana` SHALL tener "Cualquiera"
seleccionado por default. Seleccionar el default y seleccionar valores
puntuales SHALL ser mutuamente excluyente: elegir un valor puntual apaga el
default, y no dejar ningún valor puntual elegido vuelve al default.

#### Scenario: Estado inicial
- **WHEN** la pantalla de búsqueda carga
- **THEN** `Módulo` muestra "Todos" seleccionado y `Tipo de ventana` muestra
  "Cualquiera" seleccionado
- **AND** la búsqueda no manda `module_code` ni `window_type_name`

#### Scenario: Elegir varios módulos
- **WHEN** el usuario selecciona `CA` y `DF` en el listado de módulos
- **THEN** "Todos" queda deseleccionado
- **AND** la búsqueda manda `module_code=CA` y `module_code=DF`

#### Scenario: Deseleccionar todos los valores puntuales
- **WHEN** el usuario deselecciona el último módulo puntual que tenía elegido
- **THEN** el listado vuelve a mostrar "Todos" seleccionado
- **AND** la búsqueda deja de mandar `module_code`

### Requirement: La consola muestra el estado declarado cuando la ventana no está contemplada
La pantalla de búsqueda, las citas en vivo del chat y la vista previa
de ingesta SHALL renderizar `window_status` cuando el campo está
resuelto y su valor no es `Activo`. El texto SHALL ser el nombre
declarado por el catálogo (`Acceso restringido`, `En proceso de
instalación`), nunca la palabra "baja" ni el código crudo. Un hit,
una cita o un chunk vigente o sin estado SHALL NOT ganar un badge de
estado: la ausencia no se interpreta como vigente y no se inventa
una etiqueta "sin estado".

El campo viaja en el contrato ya expuesto por el servicio
(`SearchHit.window_status`, `ChunkMetadata.window_status`). La
consola SHALL espejarlo en `lib/ai-service/types.ts` antes de
leerlo. Un servicio que omite el campo SHALL degradar a no pintar
el badge, no a un error de parseo.

Un turno reabierto desde `history` SHALL NOT mostrar un estado
inventado: `CitationSnapshot` no lo trae. La consola SHALL NOT
filtrar por `window_status`: el servicio no acepta ese recorte, y
un query param ignorado se leería como exclusión.

#### Scenario: hit de una transacción no contemplada
- **WHEN** una búsqueda devuelve un hit con
  `window_status` = `Acceso restringido`
- **THEN** ese resultado muestra el texto `Acceso restringido`
- **AND** no muestra la palabra "baja"

#### Scenario: hit vigente o sin estado
- **WHEN** el hit trae `window_status` = `Activo`, o el campo está
  ausente
- **THEN** el resultado no muestra un badge de estado
- **AND** no afirma que la transacción esté vigente

#### Scenario: cita en vivo del chat
- **WHEN** un turno agentico en vivo completa y una cita trae
  `window_status` distinto de `Activo`
- **THEN** esa cita muestra el nombre declarado

#### Scenario: turno reabierto no inventa estado
- **WHEN** el operador reabre una conversación desde `history`
- **THEN** las citas de esos turnos no muestran un badge de estado
  salvo que el snapshot lo traiga

#### Scenario: vista previa de ingesta
- **WHEN** el operador sube un documento cuya ventana no está
  contemplada y el chunker estampa `window_status`
- **THEN** la vista previa muestra el nombre declarado
- **AND** no persiste el resultado

#### Scenario: no se finge un filtro
- **WHEN** el operador usa la pantalla de búsqueda o el chat
- **THEN** no hay un control que envíe `window_status` al BFF
- **AND** la consulta no recorta por estado

### Requirement: La vista previa de ingesta no persiste
La pantalla de ingesta SHALL llamar a `POST /documents/ingest` o
`POST /documents/ingest-file` y mostrar los chunks y estadísticas devueltos. NO
SHALL ofrecer ninguna acción que persista ese resultado en el corpus.

#### Scenario: subir un documento
- **WHEN** el usuario sube un archivo `.md`
- **THEN** la pantalla muestra los chunks resultantes y sus estadísticas
- **AND** no aparece ninguna fila nueva en `chunks` como consecuencia

### Requirement: La reconstrucción de corpus repite el guard de `reset`
La pantalla SHALL mantener deshabilitado el envío de una reconstrucción con
`reset=true` hasta que el usuario confirme el `tenant_id` y `doc_version`
vigentes, obtenidos de una llamada de solo lectura al servicio — nunca de un
valor escrito en el código de la UI.

#### Scenario: intento de reset sin confirmar
- **WHEN** el usuario activa el reset pero no completa la confirmación
- **THEN** el botón de envío permanece deshabilitado
- **AND** no se emite ninguna llamada a `POST /corpus/rebuild`

#### Scenario: reset confirmado
- **WHEN** el usuario completa `tenant_id` y `doc_version` coincidiendo con los
  valores vigentes
- **THEN** la pantalla envía `POST /corpus/rebuild` con `reset=true` y sus
  campos de confirmación

### Requirement: El estado de un job de reconstrucción es visible sin terminal
Tras iniciar una reconstrucción, la pantalla SHALL sondear
`GET /corpus/jobs/{id}` y mostrar `current_step`, `progress`, `status` y
`error` cuando lo haya, hasta que el job termine o falle. La lista de jobs
recientes SHALL estar disponible desde `GET /corpus/jobs`.

#### Scenario: job en curso
- **WHEN** un job de reconstrucción está corriendo
- **THEN** la pantalla refleja su paso actual y su progreso sin que el usuario
  recargue la página

#### Scenario: job fallido
- **WHEN** un job termina con `status=failed`
- **THEN** la pantalla muestra el mensaje de `error` que devuelve la API

### Requirement: Pantalla de respuesta agentica con gate humano visible
La consola SHALL exponer una pantalla de chat que llame a
`POST /answer/agentic` del servicio IA (vía Route Handler propio) y
renderice cada turno con la respuesta citada y su procedencia. Cuando el
servicio responde **202 Accepted**, ese turno SHALL mostrar las
`review_reasons`, el `thread_id`, y controles para **aprobar** o
**rechazar** la respuesta, consumiendo `POST /answer/agentic/resume`. El
turno SHALL mostrar `routing_history` — la traza de enrutamiento del
orquestador — con el campo `source` de cada decisión (`llm`, `fallback`,
`limit`). Los knobs de retrieval (módulos, tipo de ventana, `rerank`,
`split`, `lexical`) SHALL estar disponibles en la pantalla, fuera del
compositor del hilo.

#### Scenario: Respuesta completada sin pausa
- **WHEN** el usuario envía una pregunta y el grafo termina sin disparar revisión
- **THEN** el turno muestra `answer`, `citations`, `grounded` y la traza de
  enrutamiento

#### Scenario: Pausa por revisión humana
- **WHEN** el servicio responde 202 con `status=awaiting_human_review`
- **THEN** el turno muestra las razones de revisión verbatim
- **AND** ofrece acciones para aprobar o rechazar, que llaman a `/resume`

#### Scenario: Grafo no disponible
- **WHEN** el servicio responde 503 porque el grafo no compiló
- **THEN** la pantalla muestra un mensaje accionable (Postgres / checkpointer)
- **AND** no muestra JSON crudo ni traza interna

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

### Requirement: La respuesta del asistente se muestra como markdown
La pantalla de respuesta SHALL renderizar el texto del asistente como
markdown —negritas, listas, encabezados, código y tablas— en vez de mostrarlo
como texto plano. El prompt de síntesis le pide explícitamente al modelo que
estructure la respuesta y que cierre con un bloque de fuentes; mostrarla sin
formato tira esa estructura y deja los asteriscos a la vista.

El renderizado SHALL ser sin HTML crudo. El texto viene de un modelo sobre
contenido de corpus, y habilitar markup arbitrario desde una fuente que nadie
revisa es una decisión de seguridad, no de estilo.

La pregunta del usuario NO se renderiza como markdown: la escribió una
persona y sus asteriscos son literales. Los avisos del sistema —contexto
recortado, pregunta resuelta, respuesta incompleta— tampoco: no son contenido
del modelo.

#### Scenario: negritas y listas
- **WHEN** la respuesta trae `**texto**` y una lista con guiones
- **THEN** se ven en negrita y como lista
- **AND** los asteriscos y los guiones no se muestran literales

#### Scenario: el cierre de fuentes se distingue del cuerpo
- **WHEN** la respuesta termina con el bloque `Fuentes citadas:` y su lista
- **THEN** esa lista se ve como lista y no como prosa corrida

#### Scenario: HTML embebido no se ejecuta
- **WHEN** el texto de la respuesta contiene una etiqueta HTML
- **THEN** se muestra como texto
- **AND** no se inserta en el DOM como markup

#### Scenario: una tabla ancha no rompe el layout
- **WHEN** la respuesta trae una tabla más ancha que la burbuja del turno
- **THEN** la tabla scrollea horizontalmente en su propio contenedor
- **AND** la página no scrollea horizontalmente

#### Scenario: la pregunta del usuario queda literal
- **WHEN** el usuario escribe una pregunta que contiene `**`
- **THEN** el hilo muestra esos caracteres tal como los escribió

### Requirement: Una respuesta incompleta se muestra como incompleta
La pantalla de respuesta SHALL avisar cuando `answer_truncated` es true, con
el mismo peso visual que el aviso de evidencia recortada. Media respuesta
presentada como una respuesta entera es un defecto, y arreglarlo solo en el
servicio lo dejaría a medio arreglar.

El aviso SHALL decir DÓNDE se corrige —el tope de salida del perfil vigente,
editable en `/agents`— y no solo que la respuesta se cortó. Un aviso que
nombra el problema sin nombrar la palanca deja al usuario adivinando.

#### Scenario: respuesta cortada por el tope de salida
- **WHEN** un turno vuelve con `answer_truncated` en true
- **THEN** el turno muestra un aviso de que la respuesta quedó incompleta
- **AND** el aviso nombra el tope de salida del perfil como lo que hay que
  subir

#### Scenario: respuesta completa
- **WHEN** un turno vuelve con `answer_truncated` en false
- **THEN** no se muestra ningún aviso de truncado

#### Scenario: turno pausado en el gate
- **WHEN** un turno queda esperando revisión humana y su respuesta parcial
  venía cortada por el tope
- **THEN** el aviso se muestra junto a esa respuesta parcial

### Requirement: Una corrida puede elegir el perfil
La pantalla de respuesta SHALL ofrecer un selector con los perfiles
nombrados del sintetizador. Vacío o «default» SHALL omitir
`profile_id` y usar el default del servicio. Elegir un perfil SHALL
mandar su id en esa corrida y no cambiar el default.

#### Scenario: preguntar con un perfil puntual
- **WHEN** el usuario elige `Conservador` y envía una pregunta
- **THEN** el request lleva ese `profile_id`
- **AND** el default persistido no cambia

### Requirement: Un turno en vivo muestra el usage de la última completion
Cuando un turno agentico en vivo completa o pausa y el payload
trae `usage.reported=true`, el chat SHALL mostrar los tokens de
input, output y total de ese turno. Un turno cargado desde
`history` SHALL NOT mostrar cifras de tokens salvo que el
snapshot las traiga — la consola SHALL NOT escribir ceros que
se lean como una medición.

#### Scenario: turno sintetizado reporta usage
- **WHEN** el payload de un turno completado trae
  `usage.total_tokens=140` y `usage.reported=true`
- **THEN** ese turno del chat muestra 140 tokens en total

#### Scenario: turno reabierto no inventa usage
- **WHEN** el operador reabre una conversación desde `history`
- **THEN** esos turnos no muestran una línea de tokens

### Requirement: La pantalla de agentes enfoca un agente a la vez
`/agents` SHALL list the catalog as a picker and show the selected
agent's detail in a workspace. Configurable agents SHALL expose
named profiles one at a time. The system prompt, system guardrails
and the tools catalog SHALL remain available without occupying the
first screen. Deterministic agents SHALL stay read-only: role,
explanation and tools, no persona or model form.

#### Scenario: elegir un agente
- **WHEN** the operator picks a catalog entry
- **THEN** the workspace shows that agent's role, explanation and tools
- **AND** other agents' forms are not shown at the same time

#### Scenario: editar un perfil
- **WHEN** the operator picks a named profile of the synthesizer
- **THEN** they see that profile's persona, guardrails and model knobs
- **AND** the other profiles stay in the picker, not as stacked full forms

### Requirement: The agents screen shows the prompt, templates and tools
`/agents` SHALL show the synthesizer's system prompt as read-only text,
offer buttons that load the persona and operator-guardrails templates
into the matching fields without saving, let the operator edit both
fields, and show each agent's granted tools next to the tools it uses.
Deterministic agents SHALL show tools only — no prompt form.

#### Scenario: load the persona template
- **WHEN** the user clicks «Cargar template» on the persona field
- **THEN** the textarea fills with the senior insurance-analyst template
- **AND** the profile is not saved until the user confirms

#### Scenario: tools granted versus used
- **WHEN** the user looks at an agent card
- **THEN** they see tools disponibles (granted) and tools utilizadas
  (called)

### Requirement: Alta y edición de perfiles nombrados
La consola SHALL permitir crear, editar, marcar como default y borrar
perfiles nombrados del agente configurable, con nombre, persona y knobs
de modelo. La lista SHALL salir de `GET /config`, no de estado local.
Los agentes deterministas SHALL seguir siendo fichas de solo lectura
que muestran rol, explicación y herramientas del catálogo. La
consola SHALL NOT ofrecer asignar tools ni crear un nodo del grafo.

#### Scenario: crear un perfil nombrado
- **WHEN** el usuario guarda un perfil `Conservador` con una persona
- **THEN** la lista de `/agents` lo muestra
- **AND** `GET /config` lo reporta bajo `answer_synthesizer`

#### Scenario: elegir el default
- **WHEN** el usuario marca `Exhaustivo` como default
- **THEN** la pantalla lo distingue de los demás
- **AND** una corrida sin `profile_id` usa ese perfil

#### Scenario: los deterministas no tienen alta
- **WHEN** el usuario mira un agente determinista
- **THEN** ve rol, explicación y tools
- **AND** no ve un formulario de nombre ni de persona

### Requirement: El catálogo de modelos se filtra en el cliente
La pantalla de Modelos SHALL ofrecer, por proveedor, un filtro por substring
del nombre del modelo y un recorte por visibilidad (todos / ofrecidos /
ocultos). El filtro SHALL recortar la lista ya cargada: NO SHALL emitir una
llamada nueva al servicio. Con cero coincidencias, SHALL decirlo en vez de
dejar la lista vacía sin explicación.

#### Scenario: filtrar el catálogo de OpenAI
- **WHEN** el usuario escribe `gpt-5` en el filtro de OpenAI
- **THEN** la lista de ese proveedor solo muestra modelos cuyo nombre contiene
  `gpt-5`
- **AND** no se emite ninguna request de red

#### Scenario: ningún modelo coincide
- **WHEN** el filtro no coincide con ningún modelo del proveedor
- **THEN** la pantalla informa que no hay coincidencias
- **AND** no muestra filas de otros proveedores en esa lista

### Requirement: Cada proveedor conocido enlaza a su tabla de precios
Para los proveedores de la semilla (`openai`, `anthropic`, `moonshot`) la
ficha SHALL exponer un enlace externo a la página oficial donde el proveedor
publica el precio por millón de tokens. El enlace SHALL abrirse en otra
pestaña. Un proveedor que no está en esa lista SHALL no mostrar ningún
enlace de precios.

#### Scenario: ficha de OpenAI
- **WHEN** el usuario abre Configuración → Modelos
- **THEN** la ficha de OpenAI muestra un enlace a su página oficial de precios
- **AND** el enlace abre en otra pestaña

#### Scenario: proveedor sin URL conocida
- **WHEN** la ficha es de un proveedor que no está en la semilla
- **THEN** no aparece un enlace de precios

### Requirement: Cada ficha de proveedor se puede colapsar
La pantalla de Modelos SHALL permitir abrir y cerrar cada proveedor por
separado. Colapsada, la ficha SHALL seguir mostrando identidad, estado,
conteo de modelos ofrecidos, el enlace de precios si lo hay, y el switch
de habilitado. El cuerpo (credencial, catálogo, filtros) SHALL quedar
oculto. El estado de cada ficha SHALL ser independiente de las demás.

#### Scenario: colapsar OpenAI
- **WHEN** el usuario colapsa la ficha de OpenAI
- **THEN** no se ven la credencial ni la lista de modelos de OpenAI
- **AND** el nombre, el conteo de ofrecidos y el switch de habilitado siguen
  visibles

#### Scenario: las fichas no se acoplan
- **WHEN** el usuario abre Anthropic y deja OpenAI colapsada
- **THEN** solo Anthropic muestra su cuerpo
- **AND** OpenAI permanece colapsada

### Requirement: Pantalla de flujo del grafo
La consola SHALL servir `/agents/flow` con un diagrama y las fichas de
los nodos armados desde `config.flow` (nodos, `kind`, aristas,
escalera, ejemplo). La pantalla SHALL presentar los nodos en orden de
ejecución —orquestador, después `flow.ladder`, después el gate— y SHALL
mostrar en cada ficha el par entra → sale del ejemplo servido, con la
pregunta de ejemplo visible una vez arriba. El ejemplo del agente
LLM-driven y los documentos recuperados SHALL estar marcados como
ilustrativos; el resto sale de nodos deterministas. La pantalla SHALL
NOT declarar el grafo en TypeScript ni editar aristas. Si el servicio no
responde, SHALL decirlo y no inventar nodos. La navegación de
Configuración SHALL incluir esta pantalla junto a Agentes.

#### Scenario: el flujo muestra los nodos del servicio
- **WHEN** el usuario abre Configuración → Flujo
- **THEN** ve cada nodo que `GET /config` declara, con su `kind`
- **AND** las aristas coinciden con `config.flow`, no con un array local

#### Scenario: el recorrido usa una pregunta real
- **WHEN** el usuario mira la pantalla
- **THEN** ve la pregunta de ejemplo del servicio con su procedencia
- **AND** cada nodo muestra qué recibe y qué deja para esa pregunta

#### Scenario: lo que no es determinista se marca
- **WHEN** el usuario mira la ficha del sintetizador
- **THEN** su ejemplo aparece señalado como ilustrativo, porque la
  salida depende del modelo y de la persona

#### Scenario: servicio caído
- **WHEN** `GET /config` falla
- **THEN** la pantalla informa que no pudo leer el flujo
- **AND** no dibuja nodos de respaldo escritos en el cliente

### Requirement: El diagrama se deriva de las aristas servidas
El diagrama SHALL derivar su forma de hub —nodo supervisor central,
especialistas que vuelven a él, terminal sin vuelta— de `flow.edges`.
Cuando las aristas servidas no tengan esa forma, la pantalla SHALL caer
a la lista plana de aristas en vez de dibujar una topología que el
servicio no declaró.

#### Scenario: el grafo de hoy se dibuja como hub
- **WHEN** `flow.edges` trae el orquestador con vuelta desde cada
  especialista
- **THEN** el diagrama muestra el hub, sus radios y el terminal

#### Scenario: otra topología cae a la lista
- **WHEN** las aristas servidas no permiten identificar un hub
- **THEN** la pantalla lista las aristas tal como vienen

### Requirement: El administrador lee el agregado de tokens de chat del tenant
La consola SHALL exponer `/usage` al rol `administrador` (módulo
Configuración). La pantalla SHALL renderizar los totales de
`GET /api/usage/summary` (`total_calls`, `input_tokens`,
`output_tokens`, `total_tokens`) y una tabla `by_model`. Los
filtros opcionales `from`, `to`, `purpose` y `session_id` SHALL
reenviarse como query params sin una segunda capa de
validación. Al abrir la pantalla, `from` y `to` SHALL
prellenarse con el mes calendario en curso (America/Argentina/
Buenos_Aires) y la primera lectura SHALL pedir ese recorte. Un
rango invertido SHALL mostrar el 422 del servicio, no una tabla
vacía en silencio.

Un ledger vacío SHALL renderizar ceros y una frase explicativa,
no un error. Si el endpoint de arriba no existe o no responde,
la página SHALL degradar a ese estado vacío más el `error` del
BFF y SHALL NOT inventar totales desde la sesión del browser.

El browser SHALL llamar solo al Route Handler same-origin.

#### Scenario: el mes en curso es el recorte inicial
- **WHEN** un administrador abre `/usage` el 7 de septiembre
- **THEN** los filtros `from` y `to` muestran el 1 y el último
  día de septiembre
- **AND** la primera lectura pide ese rango, no el histórico
  entero

#### Scenario: ledger vacío
- **WHEN** un administrador abre `/usage` y el servicio
  devuelve ceros
- **THEN** las cards muestran 0
- **AND** la tabla se reemplaza por una frase que todavía no
  hay completions cobradas

#### Scenario: rango invertido se muestra, no se traga
- **WHEN** el administrador aplica un `from` posterior a `to`
- **THEN** la pantalla muestra el error del BFF que vino del 422
- **AND** los totales previos quedan visibles o las cards
  conservan la última lectura exitosa — SHALL NOT volverse un
  éxito falso en cero

#### Scenario: servicio sin el endpoint
- **WHEN** `GET /usage/summary` es 404 o el servicio no
  responde
- **THEN** `/usage` igual renderiza
- **AND** un aviso lleva el `error` del BFF

<!-- Promovido de: add-service-authentication -->

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

<!-- Promovido de: add-console-authentication -->

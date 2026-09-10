# web-console Delta Specification

## ADDED Requirements

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

### Requirement: La respuesta es un chat de sesión
La pantalla de respuesta SHALL presentar un hilo: cada envío appendea el
mensaje del usuario y el turno del asistente, sin pisar los turnos
anteriores de la misma sesión del browser. El compositor SHALL quedar al
pie. Cada turno SHALL seguir siendo una corrida agentica independiente
(`POST /answer/agentic/start` + sondeo de progreso). La pantalla SHALL
ofrecer empezar un hilo nuevo, que descarta el estado local y no llama al
servicio.

#### Scenario: segunda pregunta en la misma sesión
- **WHEN** el usuario envía una pregunta después de haber recibido una
  respuesta en la misma carga de la página
- **THEN** el hilo muestra ambos turnos
- **AND** el compositor queda al pie, no arriba del hilo

#### Scenario: hilo nuevo
- **WHEN** el usuario pide un chat nuevo
- **THEN** el hilo local queda vacío
- **AND** no se emite ninguna llamada al servicio

#### Scenario: gate humano en un turno
- **WHEN** una corrida responde 202 con `status=awaiting_human_review`
- **THEN** ese turno muestra las razones y las acciones de aprobar/rechazar
- **AND** los turnos anteriores del hilo siguen visibles

## MODIFIED Requirements

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

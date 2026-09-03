# web-console Delta Specification

## ADDED Requirements

### Requirement: Pantalla de respuesta agentica con gate humano visible

La consola SHALL exponer una pantalla que llame a `POST /answer/agentic` del
servicio IA (vía Route Handler propio) y renderice la respuesta citada con su
procedencia. Cuando el servicio responde **202 Accepted**, la pantalla SHALL
mostrar las `review_reasons`, el `thread_id`, y controles para **aprobar** o
**rechazar** la respuesta, consumiendo `POST /answer/agentic/resume`. La pantalla
SHALL mostrar `routing_history` — la traza de enrutamiento del orquestador —
con el campo `source` de cada decisión (`llm`, `fallback`, `limit`).

#### Scenario: Respuesta completada sin pausa

- **WHEN** el usuario envía una pregunta y el grafo termina sin disparar revisión
- **THEN** la pantalla muestra `answer`, `citations`, `grounded` y la traza de
  enrutamiento

#### Scenario: Pausa por revisión humana

- **WHEN** el servicio responde 202 con `status=awaiting_human_review`
- **THEN** la pantalla muestra las razones de revisión verbatim
- **AND** ofrece acciones para aprobar o rechazar, que llaman a `/resume`

#### Scenario: Grafo no disponible

- **WHEN** el servicio responde 503 porque el grafo no compiló
- **THEN** la pantalla muestra un mensaje accionable (Postgres / checkpointer)
- **AND** no muestra JSON crudo ni traza interna

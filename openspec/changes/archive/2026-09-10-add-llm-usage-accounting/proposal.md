## Why

Cada completion de chat **se paga**. El wrapper ya habla con dos wires
(`openai_compatible` y `anthropic_messages`), y los dos devuelven
conteos de tokens en la respuesta. Nadie los lee.

Eso no es una omisión accidental. El docstring de
`app/foundation/llm/wrapper.py` lo deja escrito: el adaptador se
quedó delgado a propósito, y *«token accounting and streaming would
each need a real consumer before they earned a layer here»*. El
consumidor ya existe — y son dos, no uno:

1. `generate_answer()` en `app/generation/rag/answer.py` (`POST /answer`).
2. `answer_synthesizer` en `app/domain/graph/agents/answer_synthesizer.py`
   (el grafo de `POST /answer/agentic`, `/start` y `/resume`).

Los dos llaman `llm.complete()` y se quedan con `text` y
`truncated`. El log `llm_complete` cuenta **caracteres**, no tokens.
Un turno que pausa en el gate y se re-sintetiza cobra dos veces y
el servicio no tiene con qué decirlo. Un eval, un rebuild y un
reranker son otros gastos; este change no los mezcla (ver
`design.md`).

Sin un asiento por llamada, el operador no puede auditar qué se
gastó, ni por modelo, ni por sesión. Contar a ojo desde la consola
del proveedor es el síntoma, no la medición.

## What Changes

- `Completion` gana un `Usage` (input / output / total, y si el
  proveedor lo **reportó**). Los dos adaptadores lo extraen del
  payload que ya llega. Si el proveedor no manda `usage`, se
  advierte y no se inventa un número.
- Un ledger en Postgres: una fila por `complete()` exitoso del
  camino HTTP. Se escribe **en el momento de la llamada**, no al
  cerrar el turno — un reject después del gate igual se pagó.
- Las respuestas de `POST /answer` y de las tres variantes
  agenticas (`200`, `202`, progreso) llevan el `usage` de la última
  completion de esa corrida. Sin llamada (contexto insuficiente):
  ceros y `reported=false`, y **cero filas**.
- `GET /usage/summary`: totales del tenant, partibles por
  `from` / `to` / `session_id` / `purpose`. Sin precio en USD.
- El script de eval sigue llamando `generate_answer` con un LLM
  pelado: no escribe asientos. El wrap se hace en el borde HTTP.

**Deliberadamente afuera:**

- **Costo en dinero.** Las tarifas cambian, hay cache tokens y
  cada proveedor cobra distinto. El ledger guarda lo que el
  proveedor reportó; el precio es otro change.
- **Embeddings y reranker.** El runner de embeddings ya acumula
  `tokens_billed` en un rebuild. Son otras APIs, otro ciclo de
  vida. No se cuelgan de este ledger.
- **`user_id`.** El servicio no autentica. Colgar un dueño de un
  header que cualquiera puede mandar mentiría. El tenant es
  `TENANT_ID`, igual que el historial de conversación.
- **Pantalla y BFF.** Este change es `-ai-service`. La consola
  espeja el contrato en un `plan-web`.
- **Uso adentro de `HistoryTurn`.** El transcript es procedencia;
  el ledger es gasto. Mezclarlos deja dos fuentes de verdad.
  Una sesión se consulta con `GET /usage/summary?session_id=`.
- **Streaming.** Sigue sin consumidor.
- **Dependencias nuevas.**

## Capabilities

### New Capabilities
- `llm-usage-accounting`: extraer, persistir y consultar el uso
  de tokens de cada completion de chat, y exponerlo en las
  respuestas que esa completion produce.

### Modified Capabilities
- Ninguna en `openspec/specs/` — `answer-generation` y
  `answer-orchestration` todavía viven como changes sin archivar.
  El campo `usage` de esas respuestas lo declara esta capability,
  no se antedata un delta sobre una spec que no es verdad actual.

## Impact

- `ai-service/app/foundation/llm/wrapper.py` — `Usage` en
  `Completion`; extracción en los dos adaptadores; el log
  `llm_complete` suma tokens.
- `ai-service/app/foundation/persistence/usage.py` — fila
  `llm_usage_events`, `UsageStore`, `RecordingLLM`.
- `ai-service/alembic/versions/*_llm_usage_events.py` — tabla +
  índices. Import en `alembic/env.py`.
- `ai-service/app/generation/rag/schemas.py` — `TokenUsage` en
  `AnswerResponse`.
- `ai-service/app/generation/rag/answer.py` — copia
  `completion.usage` a la respuesta.
- `ai-service/app/domain/schemas.py` — `usage` en el estado del
  grafo.
- `ai-service/app/domain/graph/agents/answer_synthesizer.py` —
  escribe `usage` al estado.
- `ai-service/app/domain/graph/runner.py` — wrap del LLM;
  `completed_result` / `paused_result` arrastran `usage`.
- `ai-service/app/domain/profiles.py` — `synthesizer_runtime`
  expone el `provider_id` que ya resuelve (hoy lo descarta).
- `ai-service/app/api/answer.py` y `app/api/answer_agentic.py` —
  wrap en el borde; schemas agenticos ganan `usage`.
- `ai-service/app/api/usage.py` y `app/main.py` — `GET /usage/summary`.
- `ai-service/tests/foundation/llm/test_wrapper.py` —
  extracción, usage ausente.
- `ai-service/tests/foundation/persistence/test_usage.py` —
  `RecordingLLM` y store.
- `ai-service/tests/api/test_usage_router.py` — contrato del
  summary.
- `openspec/standards/app-routes.md` — fila nueva del servicio.
  Sin cambio de estándar de ingeniería.

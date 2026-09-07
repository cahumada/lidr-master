# Diseño — ledger de completions, no un precio

El wrapper ya dijo cuándo esta capa merecía existir: cuando hubiera
un consumidor. Hay dos (`generate_answer` y `answer_synthesizer`).
Este documento fija *qué* se contabiliza y *dónde*, para que el
siguiente change no convierta el ledger en un dashboard de billing
ni lo meta adentro del transcript.

---

## 1. Extraer en el adaptador, persistir fuera

Los dos wires ya traen usage. Las formas no coinciden:

| Wire | Campos del proveedor |
|---|---|
| `openai_compatible` | `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens` |
| `anthropic_messages` | `usage.input_tokens`, `usage.output_tokens` (sin total; se suma) |

Esa diferencia es exactamente el trabajo que los adaptadores ya
hacen con `system`, `max_tokens` y el stop reason. Si cada caller
leyera el SDK, el Protocol `LLM` dejaría de ser sustituible por un
doble, y los tests de generación tendrían que fabricar un objeto
OpenAI. `Usage` viaja en `Completion`, al lado de `truncated`.

La escritura a Postgres **no** entra al adaptador. Foundation/llm
no importa SQLAlchemy; el store de chunks y el de sesiones ya
viven junto a su tabla. El ledger es otra tabla, otro lector.

## 2. Por qué una tabla y no solo el log o el JSON de la sesión

Tres alternativas, y por qué pierden:

| Alternativa | Por qué pierde |
|---|---|
| Solo `structlog` (`llm_complete` + tokens) | Un log no se consulta. Railway rota, un eval local no llega, y no hay `GET`. Eso es observabilidad, no accounting. |
| Columna / campo en `HistoryTurn` | El transcript es procedencia (respuesta + citas). El diseño de `conversation-history` ya sacó de `history` todo lo que es diagnóstico de *una* corrida (`confidence`, `routing_history`, `activity`). El gasto es de la corrida. Además un reject post-gate nunca entra a `history` y sí se pagó. |
| Sumar al cerrar el turno (`close_turn`) | El asiento llegaría tarde. El gate humano puede rechazar; un `/resume` con `adjust` re-sintetiza. El proveedor cobra en el `complete()`, no en el append del transcript. |

Una fila por llamada, escrita **ahí**, es el único momento en que
el dato y el cobro coinciden. `session_id` y `thread_id` van
nullable: `POST /answer` no tiene sesión; un agentic sin
`session_id` igual se paga.

## 3. `RecordingLLM` en el borde HTTP, no adentro de `generate_answer`

`generate_answer` tiene dos consumidores: el router y
`scripts/eval_generation.py`. El eval mide fidelidad; no es un
gasto de producción y no debe escribir asientos (ni exigir
`DATABASE_URL` para correr). El wrap se hace donde ya se resuelve
el LLM de verdad:

- `app/api/answer.py` — después de `synthesizer_runtime`.
- `app/domain/graph/runner.py` — al poner `configurable.llm`.

`RecordingLLM` delega `complete()`, persiste, y si el INSERT falla
**no** tira la respuesta. Se loguea `llm_usage_record_failed`.
Perder un asiento es un defecto de accounting; perder la respuesta
de un operador de seguros porque Postgres parpadeó es peor. El
usage igual viaja en el HTTP de esa corrida.

Un `complete()` que lanza `LLMError` no escribe fila: no hay
completion que el proveedor haya aceptado.

## 4. Qué lleva la respuesta HTTP

El body de una corrida expone el usage de **la última** completion
de esa corrida, no la suma. Un `adjust` + re-síntesis deja dos
filas en el ledger y un solo `usage` en el `200` — el de la
respuesta que se está devolviendo. Quien quiera el total de la
sesión pregunta `GET /usage/summary?session_id=`.

Sin `complete()` (hits vacíos o presupuesto agotado) el campo
igual existe: ceros y `reported=false`. Un cliente no tiene que
tratar `usage` ausente como caso especial; Swagger no muestra
`object` vacío.

`paused` (202) y el `result` de progreso también lo llevan: el
gate corre *después* del sintetizador, así que si hay prosa, hubo
llamada.

## 5. Qué no es este ledger

- **No es un precio.** Inventar USD con una tablita hardcodeada
  miente la semana que OpenAI cambia la tarifa, y no cubre
  Moonshot ni un modelo que el operador cargó a mano. Cuando haya
  que mostrar dinero, el catálogo de modelos es el lugar, no este
  change.
- **No es el gasto del corpus.** `embedding/runner.py` ya cuenta
  `tokens_billed` en el rebuild. Mezclar embeddings (batch,
  reanudable, un modelo) con chat (por request, multi-proveedor)
  es la capa vacía que el estándar prohíbe pre-construir.
- **No es atribución por usuario.** `add-console-authentication`
  lo dejó explícito: el servicio no tiene dueño verificable.
  Filtrar el ledger por un `user_id` de header sería lo mismo que
  filtrar `GET /answer/sessions` por uno — una mentira. El tenant
  del despliegue es el único corte honesto.
- **No entra a `history`.** La consola que quiera pintar tokens
  al reabrir un hilo llama al summary con el `session_id`. Eso es
  `plan-web`.

## 6. Forma de la fila

```
llm_usage_events
  id            uuid pk
  tenant_id     text not null        -- Settings.TENANT_ID
  created_at    timestamptz not null
  purpose       text not null        -- "answer" | "answer_synthesizer"
  provider_id   text not null
  model         text not null
  input_tokens  int  not null
  output_tokens int  not null
  total_tokens  int  not null
  reported      bool not null        -- false = el proveedor no mandó usage
  session_id    text null
  thread_id     text null
```

Índices: `(tenant_id, created_at DESC)` para el summary; `(session_id)`
para el corte por hilo. Nada se consulta por `model` lo bastante
como para un índice más en el primer corte.

`purpose` es un literal de código, no una fila de catálogo. Hoy
hay dos callers. El día que el planner pase a ser un LLM, es otra
fila con otro purpose, no una migración de enum.

Alembic: `env.py` tiene que importar el módulo para que
autogenerate vea la tabla. Sin ese import, la próxima
autogeneración propondría *crearla de nuevo* o no verla.

## 7. `GET /usage/summary`

Un agregado, no un listado de eventos. Nadie pagina 10.000
asientos en Swagger. Filtros opcionales (`from`, `to`,
`session_id`, `purpose`); sin filtro, todo el tenant. `from > to`
es 422.

Respuesta tipada (Pydantic, no `dict`):

```
total_calls, input_tokens, output_tokens, total_tokens
by_model: [{provider_id, model, calls, input_tokens, output_tokens, total_tokens}]
```

El router es transporte. El store agrega. El tenant no se acepta
por query: sale de `Settings.TENANT_ID`, igual que el filtro de
`chunks`.

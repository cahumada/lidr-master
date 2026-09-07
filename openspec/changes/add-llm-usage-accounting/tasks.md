# Implementation Tasks

Sin dependencias nuevas. No toca prompts, retriever ni
`HistoryTurn`. La pantalla es otro change (`plan-web`).

## 1. Extraer usage en el wrapper

- [x] 1.1 En `app/foundation/llm/wrapper.py`: dataclass `Usage`
      (`input_tokens`, `output_tokens`, `total_tokens` ≥ 0,
      `reported: bool`). `Completion` gana `usage: Usage` con
      default `Usage(0, 0, 0, reported=False)` para no romper
      los dobles de test que construyen `Completion(text=...)`.
- [x] 1.2 `OpenAICompatibleChatLLM` lee
      `response.usage.prompt_tokens` /
      `completion_tokens` / `total_tokens`. Si `usage` falta o
      algún campo viene `None`, `Usage(..., reported=False)` y
      `log.warning("llm_usage_missing", provider=..., model=...)`.
      El `log.info("llm_complete")` existente suma los tres
      enteros.
- [x] 1.3 `AnthropicChatLLM` lee `response.usage.input_tokens` /
      `output_tokens` y setea `total_tokens` = suma. Misma
      regla de ausente → `reported=False` + warning. El log
      `llm_complete` de este adaptador también suma tokens.
- [x] 1.4 Tests en `tests/foundation/llm/test_wrapper.py`: los
      fakes de `_completion` / `_message` ganan un `usage`
      opcional. Happy path de los dos wires; usage ausente
      deja `reported is False` y no rompe `truncated`; un
      `complete()` que ya existía sigue pasando con el default.

## 2. Ledger y RecordingLLM

- [x] 2.1 `app/foundation/persistence/usage.py`:
      `LlmUsageEventRow` (`llm_usage_events`) con las columnas
      de `design.md` §6. `UsageStore.record(...)` inserta una
      fila. `UsageStore.summarize(tenant_id, *, since, until,
      session_id, purpose)` devuelve el agregado. Sin raw SQL
      en el router.
- [x] 2.2 `RecordingLLM` en el mismo módulo: implementa el
      Protocol `LLM` (`model` + `complete`). Delega, y después
      de un `complete()` exitoso llama `store.record` con
      `purpose`, `provider_id`, `session_id`, `thread_id`. Si
      `record` lanza, `log.exception("llm_usage_record_failed")`
      y se devuelve el `Completion` igual. Un `LLMError` no
      escribe fila.
- [x] 2.3 Migración alembic que revisa `c4e8a91b07d2`: tabla +
      índice `(tenant_id, created_at DESC)` + índice
      `(session_id)`. Importar el módulo en `alembic/env.py`
      junto a los otros registros de `Base.metadata`.
- [x] 2.4 Tests en `tests/foundation/persistence/test_usage.py`:
      unidad de `RecordingLLM` (store doble: se llama / no se
      llama si `complete` lanza / el INSERT que falla no
      propaga). Store contra Postgres se *salta* sin
      `DATABASE_URL`: `record` + `summarize` con y sin filtros.

## 3. Respuestas de generación

- [x] 3.1 `TokenUsage` Pydantic en
      `app/generation/rag/schemas.py` (mismos campos, descriptions
      bilingües). `AnswerResponse.usage` default
      `TokenUsage(0, 0, 0, reported=False)`.
- [x] 3.2 `generate_answer` copia `completion.usage` al
      `AnswerResponse` cuando llama al LLM. Los dos returns de
      contexto insuficiente dejan el default. No recibe un
      store: el wrap vive arriba.
- [x] 3.3 `synthesizer_runtime` en `app/domain/profiles.py`
      hoy devuelve `(llm, persona, guardrails)` y tira el
      `provider_id` que ya resolvió. Exponerlo (cuarto valor del
      tuple, o un small dataclass) para no volver a leer la
      fila. `app/api/answer.py` envuelve ese LLM en
      `RecordingLLM` (`purpose="answer"`, ese `provider_id`,
      `session_id=None`, `thread_id=None`) antes de pasarlo a
      `generate_answer`. Actualizar los tres call sites
      (`answer.py`, `answer_agentic.py`, `runner.py`) al nuevo
      retorno.
- [x] 3.4 Estado del grafo en `app/domain/schemas.py`: campo
      `usage` (dict o shape estable). El sintetizador lo escribe
      desde `completion.usage` en el return. Los caminos sin
      LLM no lo tocan.
- [x] 3.5 `completed_result` y `paused_result` en
      `app/domain/graph/runner.py` copian `usage`. El runner
      envuelve el LLM de `configurable` en `RecordingLLM`
      (`purpose="answer_synthesizer"`, `session_id` y
      `thread_id` de la corrida, `provider_id` del runtime).
- [x] 3.6 Schemas de `app/api/answer_agentic.py`
      (`AnswerAgenticResponse`, `AnswerAgenticPausedResponse`,
      `AnswerAgenticProgress`) ganan `usage` con el mismo
      default. `_completed_response` / `_paused_response` lo
      mapean. El wrap **no** se duplica en el router si el
      runner ya lo hace; si `/start` arma el LLM fuera del
      runner, wrap ahí también — un solo helper
      (`llm_with_accounting`) si hay más de un call site.

## 4. Contrato GET /usage/summary

- [x] 4.1 Router delgado `app/api/usage.py`: `GET /usage/summary`.
      Query opcionales `from`, `to` (datetime), `session_id`,
      `purpose` (`answer` | `answer_synthesizer`). `from > to`
      → 422. El tenant sale de `Settings.TENANT_ID`, nunca de
      query. Response model Pydantic (`UsageSummary`,
      `UsageByModel`) — no `dict`.
- [x] 4.2 Registrar el router en `app/main.py`.
- [x] 4.3 Fila en `openspec/standards/app-routes.md` (tabla del
      servicio IA). Sin Route Handler: eso es `plan-web`.
      Ítem explícito: **sin cambios** en
      `ai-service-standards.md` ni `base-standards.md`.

## 5. Tests de contrato y cierre

- [x] 5.1 Test de router de `POST /answer` (el que ya existe en
      `tests/api/`): una completion con usage reportado aparece
      en el body; contexto insuficiente → ceros y
      `reported is False`.
- [x] 5.2 `tests/api/test_usage_router.py`: summary vacío
      (ceros); después de un record, los totales y `by_model`
      coinciden; `from > to` es 422. Store overrideado o
      skip-sin-base, el mismo patrón que
      `test_answer_session_router.py`.
- [x] 5.3 El test de wrapper de truncado y los de generación
      que construyen `Completion(text=...)` siguen verdes —
      el default de `usage` es la razón.
- [x] 5.4 `uv run pytest` y `uv run ruff check .` desde
      `ai-service/`, en verde.
- [x] 5.5 `python scripts/validate_specs.py` desde la raíz,
      sin errores.

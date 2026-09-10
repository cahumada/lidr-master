# Implementation Tasks

## 1. Contratos y settings

- [x] 1.1 `AnswerRequest` y `AnswerResponse` en `schemas.py`. `citations` es
      `list[SearchHit]`; `question` lleva `min_length=2` (la misma regla que
      `/search`). Sin dict pelado.
- [x] 1.2 Mapper compartido `search_hits_from_chunks` para que `/search` y
      `/answer` no puedan divergir en qué es una cita.
- [x] 1.3 Settings `ANSWER_MODEL`, `ANSWER_MAX_TOKENS`, `ANSWER_TEMPERATURE`.
      No reutilizar `RERANK_MODEL`. Documentarlos en `.env.example`.

## 2. Foundation

- [x] 2.1 `app/foundation/llm/wrapper.py`: wrapper delgado, cliente inyectado,
      `complete(system=, user=) -> str`. Sin red en los tests.
- [x] 2.2 `get_answer_llm()` en `dependencies.py`, mismo patrón que
      `get_embedder()`. `RuntimeError` si falta `OPENAI_API_KEY`.
- [x] 2.3 Loader Jinja2 mínimo en `app/foundation/prompts/__init__.py`
      (`StrictUndefined`, sin autoescape). Agregar Jinja2 con `uv add`.
- [x] 2.4 Prompts `answer/v1/system.j2` y `user.j2`: solo el contexto, citar
      `[document_id · section]`, declarar insuficiencia cuando no alcanza.

## 3. Generación

- [x] 3.1 `prompt_builder.py`: cada `SearchHit` entra con procedencia visible.
- [x] 3.2 `guardrails.py`: output chequea `document_id` citados contra los
      hits. Input no se duplica — se documenta por qué basta `min_length=2`.
      Marca (`grounded=false`), no rechaza.
- [x] 3.3 `answer.py`: retrieve → prompt → LLM → guardrail. Hits vacíos no
      llaman al LLM; responden insuficiencia con `grounded=true`.
- [x] 3.4 `POST /answer` thin: settings → `SearchFilters` → mismo
      `HybridRetriever.retrieve(...)` que `/search` → `generate_answer`.
- [x] 3.5 Registrar el router en `main.py`.

## 4. Tests

- [x] 4.1 `tests/foundation/llm/test_wrapper.py` con doble, sin API real.
- [x] 4.2 `tests/generation/rag/test_prompt_builder.py`.
- [x] 4.3 `tests/generation/rag/test_guardrails.py`.
- [x] 4.4 `tests/api/test_answer_router.py` con retrieval y LLM mockeados.

## 5. Evaluación de fidelidad

- [x] 5.1 `scripts/eval_generation.py`: sobre el golden set, para cada
      pregunta con `document_id` esperado, las `citations` lo incluyen.
      También `grounded_rate` cuando corre el LLM.
- [x] 5.2 `evals/GENERATION_EVAL.md`: método, métricas, resultado de la
      corrida. 2026-09-03: `citation_coverage` 94% (33/35 curated);
      muestra LLM 5/5 grounded.
- [x] 5.3 Anotar próximos pasos (UI, streaming, v2) en el README del
      servicio, no implementarlos.

## 6. Verificación

- [x] 6.1 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
      548 passed; ruff clean.
- [x] 6.2 `python scripts/validate_specs.py` en verde desde la raíz.
- [x] 6.3 No archivar: el delta se queda en `changes/` hasta que el endpoint
      esté desplegado y demostrable.

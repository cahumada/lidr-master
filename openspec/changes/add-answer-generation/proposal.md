## Why

`openspec/project.md` («Estado y alcance») declara el hueco con nombre: el
servicio recupera chunks —HybridRetriever, RRF, descomposición, reranker,
`GET /search`— pero **nadie sintetiza una respuesta**. Hoy es un buscador, no
un RAG. El criterio de aprobación del máster pide demostrar que el sistema
integra un LLM en un producto funcional, no solo que recupera texto; sin esta
capa ese criterio no se puede cumplir, por más alto que esté el `p@10`.

La recuperación ya está medida (0,171 de `p@10`, 94% de hallazgo sobre 35
preguntas reales). Lo que falta es la generación que *usa* esos chunks: un
prompt con procedencia visible, una llamada al LLM, y un guardrail que
verifique las citas contra los hits realmente recuperados — no contra lo que
el modelo diga que citó. En este dominio un `document_id` inventado es tan
peligroso como un código de transacción falso: son reglas de negocio de
seguros, y una cita que no se puede contrastar con el corpus no sirve.

## What Changes

- `POST /answer`: pregunta en lenguaje natural + los mismos filtros que
  `/search` (`module_code`, `window_type_name`, y los knobs medidos del
  pipeline). Reutiliza `HybridRetriever` / `ChunkRepository` / `SearchFilters`
  tal cual están; no se forkea la recuperación.
- Wrapper delgado de chat completions en `app/foundation/llm/wrapper.py`. El
  cliente OpenAI se construye en `get_answer_llm()` y en ningún otro lado;
  sin `OPENAI_API_KEY` levanta `RuntimeError` (como el embedder, no como el
  reranker: sin LLM no hay generación posible).
- Prompts versionados `app/foundation/prompts/answer/v1/{system,user}.j2` y
  un loader mínimo. **Jinja2 entra como dependencia**: no había ninguno en el
  repo, y el patrón del curso (prompts versionados, variables explícitas,
  `StrictUndefined` para no tragar un hueco) no se sostiene con
  `str.format`. Una sola implementación, un solo consumidor hoy; la
  versión `v1/` es lo que hace que un `v2` no pise el archivo.
- `prompt_builder` arma el contexto a partir de `list[SearchHit]`: cada
  chunk entra con documento, sección y breadcrumb a la vista, no como texto
  pelado.
- Guardrail de **salida**: una respuesta que cite un `document_id` que no
  está entre los hits recuperados se **marca** (`grounded=false`) y no se
  rechaza. El guardrail de **entrada** no se duplica: es el `min_length=2`
  que `/search` ya impone.
- Contratos `AnswerRequest` / `AnswerResponse`. `citations` es
  `list[SearchHit]` — el mismo modelo, no un segundo tipo de cita en
  paralelo. Las citas verificables son los chunks recuperados, no los
  marcadores que el LLM escribió en la prosa.
- Settings `ANSWER_MODEL`, `ANSWER_MAX_TOKENS`, `ANSWER_TEMPERATURE`.
  `RERANK_MODEL` no se reutiliza: rankear candidatos y sintetizar una
  respuesta son trabajos distintos, y tunear uno no tiene que cambiar el
  otro en silencio. El default del modelo es el mismo (`gpt-4o-mini`)
  porque no hay medición que justifique pagar más.
- Evaluación de fidelidad en `evals/` sobre el golden set: para cada
  pregunta con `document_id` esperado, las `citations` de la respuesta
  tienen que incluirlo. Método y resultado en `evals/GENERATION_EVAL.md`.
  Primera corrida (2026-09-03, 35 preguntas de `golden_curated.json`,
  pipeline medido, `--skip-llm`): **`citation_coverage` 94%** (33/35).
  Las dos fallas son de recuperación (`CO001` vs `CO001_A`; una
  compuesta cuyos tres anotados no entran al top-10), no de generación.
  Muestra con LLM (5 preguntas): `grounded_rate` 100%, `inline_hit` 80%.

**Por qué el guardrail de salida marca y no rechaza.** El campo
`citations` *es* la procedencia verificable: los `SearchHit` que devolvió
el retriever, independientes de lo que el LLM haya escrito. Rechazar con
4xx descartaría una respuesta potencialmente útil por un marcador
inventado, dejaría `grounded` sin consumidor, y haría imposible puntuar
esa pregunta en el eval de fidelidad. En seguros lo peligroso es presentar
una cita alucinada *como* procedencia verificada; esa procedencia es
`citations`, y `grounded=false` avisa que la prosa inventó algo de más.
Decidir no mostrar la respuesta es de la UI, que hoy no existe.

**Deliberadamente afuera (próximos pasos, no de este change):**

- Pantalla de `/answer` en `business-backend/`.
- Streaming de la respuesta.
- Versiones de prompt `v2` / `v3`.

## Capabilities

### New Capabilities
- `answer-generation`: sintetizar una respuesta citada a partir de los
  chunks que el pipeline de retrieval ya recupera, con un guardrail que
  marca las citas sin respaldo.

### Modified Capabilities
(ninguna — `retrieval` no cambia; este change la consume.)

## Impact

- `ai-service/app/foundation/llm/wrapper.py` — wrapper de chat completions.
- `ai-service/app/foundation/prompts/__init__.py` — loader Jinja2 mínimo.
- `ai-service/app/foundation/prompts/answer/v1/{system,user}.j2` — prompt v1.
- `ai-service/app/generation/rag/prompt_builder.py` — bloque de contexto.
- `ai-service/app/generation/rag/guardrails.py` — chequeo de citas vs. hits.
- `ai-service/app/generation/rag/answer.py` — orquestación (router + eval).
- `ai-service/app/generation/rag/schemas.py` — `AnswerRequest` / `AnswerResponse`.
- `ai-service/app/api/answer.py` — `POST /answer`, thin.
- `ai-service/app/main.py` — registra el router.
- `ai-service/app/config.py` — knobs de generación.
- `ai-service/app/dependencies.py` — `get_answer_llm()`.
- `ai-service/app/api/search.py` — usa el mapper compartido a `SearchHit`.
- `ai-service/pyproject.toml` — Jinja2 (justificado arriba).
- `ai-service/.env.example` — documenta los knobs nuevos.
- `ai-service/tests/foundation/llm/test_wrapper.py`
- `ai-service/tests/generation/rag/test_prompt_builder.py`
- `ai-service/tests/generation/rag/test_guardrails.py`
- `ai-service/tests/api/test_answer_router.py`
- `ai-service/scripts/eval_generation.py`
- `ai-service/evals/GENERATION_EVAL.md`
- `ai-service/README.md` y `openspec/project.md` — el hueco deja de serlo;
  próximos pasos anotados.
- `openspec/changes/add-answer-generation/specs/answer-generation/spec.md`
  — delta; **no se promociona a `openspec/specs/` todavía**.

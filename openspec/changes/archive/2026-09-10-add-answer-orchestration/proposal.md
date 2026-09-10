## Why

Fase 1 (`add-answer-generation`) entrega `POST /answer`: un pipeline lineal
retrieve → prompt → LLM → guardrail. Funciona, pero no puede **reintentar**
recuperación cuando el guardrail detecta citas inventadas, ni **pausar** para
revisión humana cuando la evidencia es insuficiente — un endpoint sin agentes no
tiene estado intermedio ni un punto de resume.

El curso (sesiones 13–14, rama `session_16` de LIDR-academy/ai-engineering)
resuelve esto con un supervisor LangGraph que enruta dinámicamente a agentes
especialistas, frenos deterministas (tope de pasos, guarda de legalidad,
escalera de fallback), privilegios mínimos por agente, y un gate humano que
dispara solo bajo señal — no en cada request.

Este change replica ese patrón para el dominio de este proyecto: preguntas sobre
transacciones de Visual Time, no estimación de software.

**Depende de `add-answer-generation` mergeado.** Los agentes reusan
`prompt_builder`, `check_grounding`, `get_answer_llm()`, `HybridRetriever` y
`decompose()` — no los reimplementan.

## What Changes

### Mapeo curso → proyecto

| Curso | Este proyecto | Tools |
|---|---|---|
| `requirements_extractor` | `query_planner` | 0 — `decompose()` + sugerencia de filtros |
| `budget_searcher` | `evidence_retriever` | 1 — `search_corpus` → `HybridRetriever.retrieve` |
| `estimate_generator` | `answer_synthesizer` | 0 — `prompt_builder` + `get_answer_llm()` |
| `coherence_validator` | `citation_validator` | 0 — guardrail formal + decisión de requery |
| `human_review_gate` | `answer_review_gate` | 0 — `review_reasons(state)` puro |
| `supervisor` | `orchestrator` | 0 — `Command(goto=...)` con tres frenos |

### Deliberadamente descartado (con razón)

- **`sandbox.py` + `persistence_agent`**: en el curso existen porque
  `save_estimate` es una escritura irreversible. `/answer` hoy no escribe nada;
  construir sandbox sin consumidor es abstracción prematura (`openspec/project.md`).
  Si aparece "guardar respuesta verificada por humano", ese es el momento.
- **`competition.py`**: tiene sentido para dos estimadores numéricos en desacuerdo.
  En preguntas sobre especificaciones funcionales no hay equivalente natural de
  "dos estimadores con prioridades opuestas".

### Entregables

- `app/domain/schemas.py` — `AnswerAgentState` (TypedDict) con acumuladores
  keyed para `routing_history` y `agent_contributions`.
- `app/domain/graph/orchestrator.py` — enrutamiento dinámico con tope de pasos,
  guarda de legalidad y escalera de fallback:
  `query_planner → evidence_retriever → answer_synthesizer → citation_validator`.
- Cuatro agentes en `app/domain/graph/agents/`.
- `gate.py`, `privilege.py`, `build.py`, `checkpointer.py`.
- `main.py`: compilar grafo en lifespan → `app.state.answer_graph`.
- `POST /answer/agentic` (+ resume): router thin; pausa humana → **202 Accepted**
  con `thread_id` y razones explícitas (no un 200 ambiguo).
- Tests en `tests/domain/graph/` incluyendo integración con checkpointer real
  (pausa + resume).

## Capabilities

### New Capabilities

- `answer-orchestration`: flujo agentico LangGraph sobre RAG con supervisor,
  requery ante citas inválidas, gate humano bajo señal, y privilegios mínimos.

### Modified Capabilities

- (ninguna en `openspec/specs/` todavía — delta en `changes/` hasta archivar)

## Impact

- `ai-service/pyproject.toml` — `langgraph`, `langgraph-checkpoint-postgres`
  (justificado: patrón supervisor del curso; no hay alternativa sin reimplementar
  el checkpointer y el grafo).
- `ai-service/app/domain/__init__.py`
- `ai-service/app/domain/schemas.py`
- `ai-service/app/domain/graph/checkpointer.py`
- `ai-service/app/domain/graph/orchestrator.py`
- `ai-service/app/domain/graph/build.py`
- `ai-service/app/domain/graph/gate.py`
- `ai-service/app/domain/graph/privilege.py`
- `ai-service/app/domain/graph/tools.py`
- `ai-service/app/domain/graph/agents/{query_planner,evidence_retriever,answer_synthesizer,citation_validator}.py`
- `ai-service/app/main.py`
- `ai-service/app/config.py`
- `ai-service/app/api/answer_agentic.py`
- `ai-service/.env.example`
- `ai-service/tests/domain/graph/*.py`
- `openspec/changes/add-answer-orchestration/specs/answer-orchestration/spec.md`

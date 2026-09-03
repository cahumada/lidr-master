# Implementation Tasks

## 1. OpenSpec

- [x] 1.1 `proposal.md` con dependencia de `add-answer-generation`, mapeo de
      roles, y razones de descarte (sandbox, competition).
- [x] 1.2 Delta `specs/answer-orchestration/spec.md`.

## 2. Dependencias y contratos

- [x] 2.1 Agregar `langgraph` y `langgraph-checkpoint-postgres` vía `uv add`.
- [x] 2.2 `AnswerAgentState` en `app/domain/schemas.py` con acumuladores keyed.
- [x] 2.3 Settings de orquestación en `config.py` + `.env.example`.

## 3. Grafo

- [x] 3.1 `privilege.py` — tabla mínima; `evidence_retriever` UNA tool.
- [x] 3.2 `tools.py` — `search_corpus` envuelve `HybridRetriever.retrieve`.
- [x] 3.3 Cuatro agentes reutilizando piezas de fase 1.
- [x] 3.4 `orchestrator.py` — tres frenos deterministas.
- [x] 3.5 `gate.py` — `review_reasons` puro + `answer_review_gate`.
- [x] 3.6 `build.py` + `checkpointer.py`.
- [x] 3.7 Lifespan en `main.py` → `app.state.answer_graph`.

## 4. API

- [x] 4.1 `POST /answer/agentic` thin — invoca grafo, 202 en pausa humana.
- [x] 4.2 `POST /answer/agentic/resume` — continúa con decisión humana.

## 5. Tests

- [x] 5.1 `test_state.py`, `test_orchestrator_routing.py`, `test_privilege.py`.
- [x] 5.2 Tests por agente + `test_gate.py`.
- [x] 5.3 Integración con checkpointer (pausa + resume), marcada `integration`.

## 6. Verificación

- [x] 6.1 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
- [x] 6.2 `python scripts/validate_specs.py` en verde desde la raíz.
- [ ] 6.3 Smoke manual: pregunta fuera del corpus → pausa → resume completa.
- [ ] 6.4 No archivar hasta smoke de pausa/resume verificado.

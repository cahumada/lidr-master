# Implementation Tasks

## 1. OpenSpec

- [x] 1.1 `proposal.md` con el mapeo al `Agents::Profile` del curso, la razón
      del hueco (un solo agente LLM-driven) y lo descartado con su razón.
- [x] 1.2 Delta `specs/agent-profiles/spec.md`.

## 2. Catálogo

- [x] 2.1 `app/domain/graph/catalog.py`: `AgentSpec` por nodo con rol,
      explicación, `kind`, `llm_driven` y `config_source`; `tools` derivado de
      `AGENT_PRIVILEGES`, no repetido.
- [x] 2.2 `configurable_agent_keys()` — solo los LLM-driven.
- [x] 2.3 Test de drift: el catálogo cubre exactamente los nodos del grafo
      compilado (`tests/domain/graph/test_catalog.py`).

## 3. Persistencia

- [x] 3.1 `app/domain/profiles.py`: `AgentProfileRow` (una fila por agente,
      knobs nullable), `AgentProfileRepository` (get/all/upsert/delete con
      `ON CONFLICT DO UPDATE`), `resolve_agent_config` y
      `synthesizer_runtime`.
- [x] 3.2 Migración `b15380641ff9`. **Los `drop_table` que el autogenerate
      propuso sobre las tablas del checkpointer de LangGraph se sacaron a
      mano** y `alembic/env.py` ahora las excluye con `include_name`.
- [x] 3.3 Settings `ANSWER_MODEL_CATALOG` y `AGENT_PERSONA_MAX_CHARS`.

## 4. API

- [x] 4.1 `GET /config` — catálogo + config vigente + `sources` por valor +
      catálogo de modelos + tope de persona.
- [x] 4.2 `PUT /config/agents/{agent_key}` — upsert con validación: 404
      desconocido, 422 determinista, 422 modelo fuera del catálogo, 422
      persona sobre el tope, temperatura 0..2 y tope de tokens 1..8192 por
      schema.
- [x] 4.3 `DELETE /config/agents/{agent_key}` — vuelve a los defaults.
- [x] 4.4 Router registrado en `main.py`.

## 5. Aplicar el perfil

- [x] 5.1 `build_answer_llm(model, max_tokens, temperature)` cacheado, con el
      cliente de OpenAI armado una sola vez.
- [x] 5.2 Bloque de persona en `answer/v1/system.j2`, después de las reglas y
      subordinado a ellas.
- [x] 5.3 `persona` por `build_messages` y `generate_answer`.
- [x] 5.4 `synthesizer_runtime` como único punto de resolución para
      `/answer`, `/answer/agentic` y el runner; el grafo lo recibe por config
      y el agente no toca la base.

## 6. Tests

- [x] 6.1 `tests/domain/test_profiles.py` — merge, override parcial,
      temperatura 0.0 como override (no como ausencia), persona vacía.
- [x] 6.2 `tests/domain/graph/test_catalog.py` — drift contra el grafo,
      privilegios, solo el sintetizador es LLM-driven.
- [x] 6.3 `tests/api/test_config_router.py` — GET/PUT/DELETE y las cuatro
      validaciones.
- [x] 6.4 `tests/generation/rag/test_prompt_builder.py` — sin persona el
      prompt es idéntico; con persona va después de las reglas.
- [x] 6.5 `tests/api/conftest.py` — stub de `synthesizer_runtime` para que los
      tests de API sigan sin base ni red.

## 7. Consola web

- [x] 7.1 Tipos `ServiceConfig`, `AgentConfig`, `EffectiveAgentConfig`,
      `ConfigSources`, `AgentProfileUpdate`.
- [x] 7.2 `lib/ai-service/config.ts` + `putJson`/`deleteJson` en el base client.
- [x] 7.3 Route Handlers `GET /api/config` y
      `PUT|DELETE /api/config/agents/[agentKey]` (la validación queda en el
      servicio; el proxy transporta sus 404/422).
- [x] 7.4 Pantalla `/agents`: formulario para el configurable (persona con
      contador contra el tope, modelo del catálogo, temperatura, tope de
      tokens, "volver a los defaults") y fichas read-only para los
      deterministas diciendo por qué no aplican. Nav + portada.

## 8. Documentación

- [x] 8.1 `ai-service/README.md` — sección de perfiles de agente.
- [x] 8.2 `business-backend/README.md` — la pantalla `/agents`.
- [x] 8.3 `README.md` de la raíz — mención en la arquitectura.
- [x] 8.4 `.env.example` — los dos settings nuevos.

## 9. Verificación

- [x] 9.1 `uv run pytest` y `uv run ruff check .` en verde (592 sin
      integración).
- [x] 9.2 `pnpm lint` y `pnpm build` en verde.
- [x] 9.3 `python scripts/validate_specs.py` en verde.
- [x] 9.4 Smoke real en el browser: guardar persona + `gpt-4o` + temperatura
      0.3 desde `/agents` → `GET /config` reporta los tres como `profile` y
      el tope de tokens como `settings` (override parcial) → `POST /answer`
      responde 200 con el modelo del perfil → "volver a los defaults" deja
      todo en `settings`.
- [ ] 9.5 No archivar hasta que el despliegue esté verificado de punta a punta.

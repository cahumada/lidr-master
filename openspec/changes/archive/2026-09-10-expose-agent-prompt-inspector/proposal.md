## Why

En `/agents` se edita la persona y el modelo del sintetizador, pero no se
ve el system prompt que realmente se manda, no hay un template de voz
para un analista funcional de seguros, los guardrails de operador no se
pueden escribir aparte de la persona, y las tools se listan sin distinguir
cuáles están concedidas de cuáles el nodo llama. Quien configura el agente
LLM no puede auditar qué instrucciones fijas tiene delante ni qué
herramientas existen en el sistema.

## What Changes

- `GET /config` sirve el system prompt base del sintetizador (`answer/v1`),
  la lista de guardrails de sistema (prompt + `check_grounding`), un
  template de persona (analista funcional sr. de seguros) y un template
  de guardrails de operador.
- Cada agente reporta `tools` (concedidas) y `tools_used` (las que el
  código llama). El config también lista el catálogo global de tools.
- El perfil nombrado gana un knob `guardrails` (texto, tope igual que
  persona) que se appendea al system prompt en un bloque propio, después
  de las cinco reglas y subordinado a ellas — igual que `persona`.
- La consola `/agents` muestra el prompt, deja cargar los templates,
  edita persona y guardrails, y muestra tools disponibles vs utilizadas.
- Los guardrails de código (`check_grounding`, las cinco reglas del
  template) NO se editan: un setting que los apague rompería el eval de
  fidelidad.

### Deliberadamente descartado

- **Editar el system prompt desde la UI.** Es la fuente de las reglas de
  grounding; un textarea que las pise es un override que el eval no
  puede comparar.
- **Asignar tools desde la UI.** Siguen saliendo de `AGENT_PRIVILEGES`.
- **Apagar `check_grounding`.** Es el único chequeo verificable de
  procedencia.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `agent-profiles`: el config expone prompt, templates, tools used y
  guarda `guardrails` por perfil.
- `web-console`: `/agents` visualiza el prompt, carga templates, edita
  guardrails de operador y muestra tools disponibles/utilizadas.
- `answer-generation`: el system prompt acepta el bloque de guardrails
  de operador, subordinado a las reglas.

## Impact

- `ai-service/app/domain/graph/catalog.py` — `tools_used`, catálogo de tools
- `ai-service/app/domain/graph/inspector.py` — prompt, templates, guardrails de sistema
- `ai-service/app/foundation/prompts/answer/v1/system.j2` — bloque `guardrails`
- `ai-service/app/generation/rag/prompt_builder.py`, `answer.py`
- `ai-service/app/domain/profiles.py` — columna y merge
- `ai-service/alembic/versions/` — migración
- `ai-service/app/api/config.py` — campos nuevos en GET/PUT
- `ai-service/app/domain/graph/agents/answer_synthesizer.py`, `runner.py`
- `ai-service/app/api/answer.py`, `answer_agentic.py`
- `business-backend/app/agents/agents-console.tsx`
- `business-backend/lib/ai-service/types.ts`

# Implementation Tasks

## 1. OpenSpec

- [x] 1.1 `proposal.md` y `design.md` con lo que se muestra, lo que se
      edita y lo descartado.
- [x] 1.2 Deltas de `agent-profiles`, `web-console` y `answer-generation`.

## 2. Servicio — inspección

- [x] 2.1 Catálogo: `tools_used` por nodo; catálogo global de tools con
      descripción, `granted_to` y `used_by`.
- [x] 2.2 Inspector: system prompt base (`answer/v1`), guardrails de
      sistema (prompt + código), templates de persona y de guardrails
      de operador.
- [x] 2.3 `GET /config` sirve lo anterior en el sintetizador, en cada
      agente (`tools` / `tools_used`) y a nivel raíz (`tools`,
      templates). Tests de drift.

## 3. Servicio — guardrails de operador

- [x] 3.1 Columna `guardrails` en `agent_profiles` + merge en
      `resolve_agent_config` (null = unset). Tope = persona.
- [x] 3.2 El template `answer/v1/system` appendea el bloque, subordinado
      a las cinco reglas. Sin guardrails el prompt queda byte-idéntico.
- [x] 3.3 `synthesizer_runtime` y los tres caminos de síntesis pasan
      `guardrails` al prompt. Tests.

## 4. Consola

- [x] 4.1 Tipos + `/agents`: prompt de solo lectura, persona con
      «Cargar template», guardrails de operador editables con template,
      tools disponibles vs utilizadas.
- [x] 4.2 Los deterministas muestran tools concedidas y usadas, sin
      formulario de prompt.

## 5. Verificación

- [x] 5.1 `uv run pytest` y `uv run ruff check .` desde `ai-service/`.
- [x] 5.2 `pnpm lint` desde `business-backend/`.
- [x] 5.3 `python scripts/validate_specs.py` desde la raíz.

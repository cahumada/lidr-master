# Implementation Tasks

## 1. Prompts

- [x] 1.1 Reescribir `answer/v1/system.j2`: rol que cubre el registro
      funcional y el técnico (la persona no se pisa), cinco reglas (solo
      contexto, cierre `Fuentes citadas:`, frase de insuficiencia intacta,
      no inventar, español) más el bloque de redacción (síntesis, no volcado).
- [x] 1.2 Reescribir `answer/v1/user.j2` para que no pida citas inline.
- [x] 1.3 Aplicar las mismas reglas a `answer/v2` y conservar el bloque de
      memoria, declarado no-procedencia.
- [x] 1.4 Actualizar el guardrail de inspector `cite_provenance` para que
      describa el cierre, no la cita por afirmación.

## 2. Tests y docs

- [x] 2.1 Tests del prompt: instruye `Fuentes citadas`, prohíbe el marcador
      en el cuerpo, pide prosa y no un volcado; el user prompt no dice
      «citá con esos identificadores». El rol base nombra ambos registros
      y no se presenta como analista funcional.
- [x] 2.2 Los tests de subordinación (persona, guardrails, memoria) siguen
      pasando: las reglas van primero.
- [x] 2.3 `GET /config` expone el prompt nuevo y el guardrail actualizado.
- [x] 2.4 README: la persona no puede hacer omitir el cierre de fuentes.

## 3. Verificación

- [x] 3.1 `python scripts/validate_specs.py` desde la raíz.
- [x] 3.2 `uv run pytest` y `uv run ruff check .` desde `ai-service/`.

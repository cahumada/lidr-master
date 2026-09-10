## Why

El system prompt `answer/v1` (y `v2` con memoria) obliga a citar cada
afirmación como `[document_id · section]`. En este servicio esa instrucción
está mal puesta: la procedencia verificable **ya es** `citations` —los
`SearchHit` que entraron al prompt— y la consola los muestra como
«Evidencia recuperada». El marcador inline no alimenta el contrato; solo
empuja al modelo a redactar como un listado de chunks etiquetados.

Dos fallas se ven en las respuestas reales. La primera: la prosa copia o
parafrasea bloques en vez de explicar la pregunta. La segunda: `inline_hit`
ya flaqueó en COL502 (el modelo no nombró el código) precisamente porque
citar el marcador y nombrar la transacción son trabajos distintos, y el
prompt los mezclaba.

El operador pidió el cierre opuesto: el cuerpo es una explicación; al final
de toda la respuesta, las fuentes usadas.

## What Changes

- `answer/v1` y `answer/v2` (system + user) instruyen: responder solo con el
  contexto, redactar una explicación continua (no reenviar bloques), no
  citar `[document_id · section]` en el cuerpo, y cerrar con
  `Fuentes citadas:` y los `document_id` realmente usados.
- El rol del system prompt **no** es «analista funcional»: esa voz (y la
  técnica) vive en el perfil de agente. El rol base cubre los dos
  registros del corpus —funcional y técnico— y declara que el perfil
  ajusta la voz, no el alcance.
- Siguen siendo **cinco reglas**. La frase de insuficiencia no se toca
  (`INSUFFICIENT_CONTEXT_MESSAGE`). Persona y guardrails siguen
  subordinados a ellas.
- El user prompt deja de decir «citá con esos identificadores»: system y
  user no pueden contradecirse.
- El guardrail de inspector `cite_provenance` describe el cierre, no la
  cita por afirmación. `check_grounding` **no se toca**: sin marcadores
  inline una respuesta sigue `grounded=true`; un marcador inventado que el
  modelo igual escriba sigue marcando `grounded=false`.
- `v1` / `v2` se editan in-place. El corte de versión en este repo distingue
  memoria (`v2`) de no-memoria (`v1`), no generaciones del texto de las
  reglas. Un `v3` obligaría a `add-conversation-memory` a pinnear otra
  versión para el mismo invariante («sin sesión es v1 byte a byte»).

**Deliberadamente afuera:**

- Parsear `Fuentes citadas:` en `check_grounding`. Ampliar el regex es un
  change aparte; hoy el guardrail solo observa el patrón
  `[document_id · section]`.
- Cambiar `citations` del contrato ni la lista de evidencia de la consola.
  El cierre de la prosa es un subset usado; `citations` sigue siendo lo que
  el modelo vio.
- Re-correr el eval de fidelidad. `citation_coverage` no depende de la
  prosa; `inline_hit` va a bajar y eso es esperado.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `answer-generation`: el prompt instruye síntesis + cierre de fuentes, no
  cita inline por afirmación.

## Impact

- `ai-service/app/foundation/prompts/answer/v1/{system,user}.j2`
- `ai-service/app/foundation/prompts/answer/v2/{system,user}.j2`
- `ai-service/app/domain/graph/inspector.py` — texto de `cite_provenance`
- `ai-service/tests/generation/rag/test_prompt_builder.py`
- `ai-service/tests/api/test_config_router.py`
- `ai-service/README.md` — la persona no puede convencer al modelo de
  omitir el cierre de fuentes
- `openspec/changes/revise-answer-synthesis-prompt/specs/answer-generation/spec.md`

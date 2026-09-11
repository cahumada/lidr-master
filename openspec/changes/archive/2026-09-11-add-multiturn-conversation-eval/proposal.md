## Why

El resolver de preguntas referenciales de `conversation-memory` está medido en
**una sola dirección**. Su `design.md` lo dice: se sabe que no reescribe cuando
no hay referente (el falso positivo), y no se sabe con qué frecuencia deja sin
resolver una pregunta que sí tenía referente (el **falso negativo**).

Y el eval de generación pasa por `generate_answer`, no por el grafo. Eso deja
sin medir todo lo que el grafo agrega: la resolución del planner, los anchors
aplicados, el presupuesto compartido entre memoria y evidencia, y el gate.

Esta tarea nació anotada dentro de `add-conversation-memory` como
*"(nuevo, NO de este change)"*, y ahí bloqueaba el archivado de un change cuyo
código está terminado. Sale a su propio lugar en lugar de seguir colgada.

## What Changes

- Un **golden set multi-turno**: secuencias de preguntas donde la segunda
  depende de la primera, con la reescritura esperada anotada a mano.
- Medir el **falso negativo** del resolver: cuántas preguntas con referente real
  quedan sin resolver, que es la dirección que hoy no se mide.
- Medir la **calidad de la reescritura**, no solo si hubo reescritura.
- Un eval que corra **por el grafo** (`/answer/agentic/start` + progreso) en vez
  de por `generate_answer`, para que lo que se mide sea lo que el usuario recibe.

## Capabilities

Ninguna nueva. Es medición sobre `conversation-memory` y `answer-orchestration`
ya especificadas; si la medición destapa un comportamiento que las specs no
declaran, eso es un change aparte.

## Impact

- `ai-service/evals/` — el golden set multi-turno, nuevo.
- `ai-service/scripts/` — el runner que pasa por el grafo.
- `openspec/specs/conversation-memory/spec.md` — solo si la medición cambia lo
  que el documento afirma.

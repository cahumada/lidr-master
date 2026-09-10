# Implementation Tasks

## 1. El golden set
- [ ] 1.1 Secuencias de al menos dos turnos en `evals/`, con la pregunta escrita,
  la reescritura esperada y los `document_id` que la respuesta debería citar.
- [ ] 1.2 Incluir los tres casos que importan: referente claro, referente
  ausente (no debe reescribir) y referente ambiguo.
- [ ] 1.3 Revisión humana del set antes de reportar cualquier número — la misma
  regla que la spec de `retrieval` fija para el golden de recuperación.

## 2. La medición
- [ ] 2.1 Falso negativo del resolver: preguntas con referente real que quedaron
  sin resolver, sobre el total de las que lo tenían.
- [ ] 2.2 Calidad de la reescritura, no solo su presencia.
- [ ] 2.3 Reportar las dos direcciones juntas. Un número solo vuelve a dejar el
  hueco que este change existe para cerrar.

## 3. El runner
- [ ] 3.1 Un eval que corra por el grafo (`/answer/agentic/start` + progreso) y
  no por `generate_answer`, para medir lo que el usuario recibe.
- [ ] 3.2 Anotar en el resultado qué anchors se aplicaron y si la memoria
  desplazó evidencia (`dropped_hits`).

## 4. Cierre
- [ ] 4.1 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
- [ ] 4.2 `python scripts/validate_specs.py` sin errores.
- [ ] 4.3 Actualizar `openspec/specs/conversation-memory/spec.md` solo si la
  medición contradice lo que hoy afirma.

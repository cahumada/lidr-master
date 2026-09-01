# Tareas de implementación

## 1. Reproducir y fijar la evidencia

- [ ] 1.1 `scripts/audit_dangling_chunks.py`: recorre `data/chunks/*.json` y
      reporta enunciados colgados, sus continuaciones, y los documentos
      afectados. Es el que produce los números del `proposal.md` y el que
      verifica que bajen después del cambio.
- [ ] 1.2 Fixtures del corpus real en `tests/generation/rag/chunking/fixtures/`:
      el condicional de `PRODUCERS_AGL009` (`§Si` / `·` / `De lo contrario,` /
      `·`) y el lead-in con contenido de `CPL502`
      (`· De la tabla ... se obtiene:` / `o La condición ante el IVA ...`).
- [ ] 1.3 Test de regresión que hoy FALLA: el condicional de AGL009 produce un
      solo chunk con las dos ramas. Dejarlo rojo antes de tocar el chunker.

## 2. Detección del enunciado colgado

- [ ] 2.1 `_leaves_statement_open(unit_text) -> bool` en `functional_spec.py`:
      la última línea no vacía, sin markup de énfasis, termina en `,` o `:`.
- [ ] 2.2 Test: `No aplica.`, `A petición del usuario.` y `Volver a ejecutar.`
      NO son enunciados colgados — la protección de las 291 respuestas cortas
      es explícita, no incidental.
- [ ] 2.3 Test: `De lo contrario,` y `· De la tabla ... se obtiene:` SÍ lo son.

## 3. Unión hacia adelante en la segmentación

- [ ] 3.1 En `_segment_prose`, después de segmentar: unir cada unidad con
      enunciado colgado a las que siguen, hasta que una cierre el enunciado.
      La unión NO cruza el borde de la sección.
- [ ] 3.2 La última unidad de una sección que queda colgada se emite tal cual —
      no hay hacia adelante al cual unirla.
- [ ] 3.3 Test: el orden del fuente se preserva; unir nunca reordena.
- [ ] 3.4 Test: una sección sin enunciados colgados produce exactamente los
      mismos chunks que hoy (no hay cambio de comportamiento colateral).

## 4. El residuo que no entra bajo el techo

- [ ] 4.1 `continued_from` y `continues_into` (`str | None`) en
      `ChunkMetadata`, con la convención bilingüe EN || ES y descripción en el
      schema OpenAPI.
- [ ] 4.2 Cuando la unión excedería el cap, emitir los chunks separados y
      enlazarlos con esos dos campos, en vez de unir a la fuerza o partir.
- [ ] 4.3 Test: un grupo que no entra produce N chunks enlazados en cadena, y
      ningún chunk supera `NARRATIVE_CHUNK_TOKEN_CAP`.
- [ ] 4.4 Test: los campos quedan ausentes —no cadena vacía— en un chunk normal.

## 5. Verificación sobre el corpus

- [ ] 5.1 Regenerar `data/chunks/` y correr `audit_dangling_chunks.py`:
      los 1.058 enunciados colgados deben caer a 53 o menos (los que no entran
      bajo el techo), y esos deben llevar `continues_into`.
- [ ] 5.2 Ningún documento pierde chunks fuera de lo previsto: el total baja
      ~1.066 (−1,72%) y ningún documento pasa a producir cero chunks.
- [ ] 5.3 Comparar 20 chunks unidos contra su fuente a mano: la rama else y su
      condición viajan juntas.
- [ ] 5.4 Anotar en `openspec/domain/` que el export usa `·`/`o`/`§` como
      niveles de viñeta de Word y que el glifo predice la profundidad solo el
      ~79% de las veces [VERIFICADO-CORPUS] — es conocimiento sobre el sistema
      fuente, y el próximo que quiera anidar por glifo necesita ese número.

## 6. Cierre

- [ ] 6.1 `uv run pytest`, `uv run ruff check .`,
      `uv run python scripts/validate_specs.py` en verde.
- [ ] 6.2 Integrar los deltas en `openspec/specs/` y archivar el cambio.

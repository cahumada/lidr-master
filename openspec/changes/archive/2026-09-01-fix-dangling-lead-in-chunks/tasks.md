# Tareas de implementación

## 1. Reproducir y fijar la evidencia

- [x] 1.1 `scripts/audit_dangling_chunks.py`: recorre `data/chunks/*.json` y
      reporta enunciados abiertos, cuáles quedaron enlazados y los documentos
      afectados. Es el que produce los números del `proposal.md` y el que
      verifica que bajen después del cambio.
- [x] 1.2 Fixtures en `tests/generation/rag/fixtures/`: el condicional de
      `PRODUCERS_AGL009` (`§Si` / `·` / `De lo contrario,` / `·`), el lead-in
      con contenido de `CPL502`, las respuestas cortas de `CPL500`, y un
      `over_cap_statement.md` sintético para el residuo que no entra bajo el
      techo.
- [x] 1.3 Test de regresión rojo antes del arreglo: verificado desactivando la
      unión — `test_the_agl009_connector_travels_with_the_branch_it_introduces`
      y `test_the_cpl502_lead_in_travels_with_what_closes_it` fallan sin ella.

## 2. Detección del enunciado abierto

- [x] 2.1 `_leaves_statement_open(unit_text)` en `functional_spec.py`: la
      última línea no vacía, sin markup de énfasis, termina en `,` o `:`.
- [x] 2.2 Test: `No aplica.`, `A petición del usuario.` y `Volver a ejecutar.`
      NO dejan el enunciado abierto — la protección de las 291 respuestas
      cortas es explícita, no incidental.
- [x] 2.3 Test: `De lo contrario,` y `### · _De la tabla ... se obtiene:_` SÍ.
      Incluye el caso del `:` adentro de la itálica del export.

## 3. Unión hacia adelante en la segmentación

- [x] 3.1 `_join_open_statements` se aplica al final de `_segment_prose`, así
      que corre en cada nivel del descenso. No cruza el borde de la sección
      porque `_segment_prose` recibe el cuerpo de una sección.
- [x] 3.2 La última unidad de una sección que queda abierta se emite tal cual.
- [x] 3.3 Test: el orden del fuente se preserva; unir nunca reordena.
- [x] 3.4 Verificado que no hay cambio colateral: los 191 tests previos siguen
      en verde, y la comparación del corpus completo no muestra ningún
      documento perdido ni ninguno que pase a cero chunks.

## 4. El residuo que no entra bajo el techo

- [x] 4.1 `continued_from` y `continues_into` (`str | None`) en
      `ChunkMetadata`, con la convención bilingüe EN || ES y descripción en el
      schema OpenAPI.
- [x] 4.2 `_link_split_statements` enlaza los chunks vecinos cuando la unión no
      entró bajo el techo, en vez de unir a la fuerza o descartar.
- [x] 4.3 Test: el fixture sobre el techo produce una cadena enlazada en ambos
      sentidos, ningún chunk supera el cap, ningún enlace cruza de sección ni
      apunta a sí mismo.
- [x] 4.4 Test: los campos quedan ausentes en un chunk con enunciado completo.

## 5. Verificación sobre el corpus

- [x] 5.1 Corpus regenerado (2169 archivos) y auditado: los enunciados abiertos
      bajan de **1.090 a 92**, de los cuales 70 llevan `continues_into` y 22
      son la última unidad de su sección. Escrito a un directorio aparte para
      no pisar `data/chunks`, que sigue siendo el artefacto de la corrida
      anterior hasta que se decida regenerarlo.
- [x] 5.2 Sin pérdidas: 2213 documentos antes y después, ninguno perdido,
      ninguno en cero chunks, ningún chunk narrativo sobre el techo de 500,
      ningún enlace apuntando a un chunk inexistente. Total 61.901 → 60.451
      (−1.450, −2,34%).
- [x] 5.3 Muestras comparadas contra el fuente: `AGL009` (el conector viaja con
      su rama), `CPL502` (el lead-in viaja con lo que lo cierra), `CPL018` y
      `CPL501` (cadenas enlazadas de 472–490 tokens), y `OP714`, donde el
      enunciado abierto sin enlace es un truncamiento del propio export.
- [x] 5.4 `openspec/domain/word-export-bullet-glyphs.md`: los glifos `·`/`o`/`§`
      son niveles de viñeta de Word y predicen la profundidad solo el 78,8% de
      las veces [VERIFICADO-CORPUS], con las tablas de transiciones.

## 6. Cierre

- [x] 6.1 `pytest` (217), `ruff check .` y `validate_specs.py` en verde.
- [x] 6.2 Deltas integrados en `openspec/specs/` y cambio archivado.
- [ ] 6.3 Regenerar `data/chunks` y volver a correr embeddings — decisión del
      dueño del repo, porque invalida ~2.000 filas del sidecar actual.

# document-chunking Delta Specification

## ADDED Requirements

### Requirement: Una unidad que deja el enunciado colgado NO DEBE emitirse sola
Una unidad narrativa cuyo texto termina en `,` o en `:` no cerró su enunciado:
continúa en la unidad siguiente. Emitirla sola produce dos chunks incompletos y,
cuando el enunciado es un condicional, algo peor que incompleto — la rama else
recuperada sin su conector se lee como la rama then e invierte la regla de
negocio.

El discriminador es **gramatical, no de largo**. `No aplica.` y `A petición del
usuario.` son cortas pero cierran su oración, y quedan intactas; `· De la tabla
de Situación impositiva del Cliente se obtiene:` es larga y no cierra nada.

La unión avanza hasta que una unidad cierra el enunciado, y NO DEBE cruzar el
borde de la sección: dos secciones distintas no se continúan una a la otra.

#### Scenario: Conector entre las dos ramas de un condicional
- **WHEN** una sección contiene `§Si <condición>`, `·<rama then>`,
  `De lo contrario,` y `·<rama else>` como unidades consecutivas
- **THEN** las cuatro se emiten como un solo chunk
- **AND** ninguna rama puede recuperarse sin su condición

#### Scenario: Lead-in con contenido seguido de sus hijos
- **WHEN** una unidad termina en `:` y las siguientes son sus ítems
- **THEN** el lead-in y sus ítems quedan en el mismo chunk

#### Scenario: Respuesta corta que sí cierra su oración
- **WHEN** el contenido de una unidad es `No aplica.` o `A petición del usuario.`
- **THEN** se emite como su propio chunk, sin unirse a nada

#### Scenario: Enunciado colgado al final de la sección
- **WHEN** la última unidad de una sección deja el enunciado colgado
- **THEN** se emite tal cual, porque no hay unidad siguiente en esa sección

### Requirement: Un enunciado que no entra bajo el techo DEBE marcarse, no partirse en silencio
Cuando unir las unidades de un enunciado excedería
`NARRATIVE_CHUNK_TOKEN_CAP`, los chunks se emiten separados y cada uno DEBE
declarar a su vecino en la metadata: `continues_into` apunta al chunk donde el
enunciado termina, `continued_from` al chunk donde empieza.

Unir a la fuerza rompería la garantía de que ningún chunk supera el techo, que
la capa de embeddings verifica antes de la primera llamada a la API. Descartar
uno de los dos borraría una regla de negocio. Marcar deja la decisión al
retrieval, igual que marcar un documento índice en vez de tirarlo.

#### Scenario: Grupo que excede el techo
- **WHEN** las unidades de un enunciado suman más que el techo de tokens
- **THEN** se emiten como chunks separados, ninguno por encima del techo
- **AND** cada uno lleva `continues_into` / `continued_from` con el `chunk_id`
  de su vecino en el enunciado

#### Scenario: Chunk que no continúa en ningún lado
- **WHEN** un chunk contiene un enunciado completo
- **THEN** `continued_from` y `continues_into` están ausentes de su metadata

## MODIFIED Requirements

### Requirement: Narrative chunking SHALL keep a bullet with its children under a token cap
The unit is the top-level bullet together with all of its nested children — a
child SHALL never be separated from its parent, since a nested condition read
without its parent inverts the business rule. A section small enough stays a
single chunk. A unit over the cap descends one bullet level and repeats.

Antes de medir contra el techo, las unidades que dejan el enunciado colgado se
unen con las que siguen (ver *Una unidad que deja el enunciado colgado NO DEBE
emitirse sola*). El orden importa: unir primero y medir después evita que una
unidad quede fuera del grupo por un techo calculado sobre medio enunciado.

The token budget for a unit is computed from ITS OWN contextual header, which
grows with the breadcrumb path while descending; a budget estimated once at the
top would let a long breadcrumb silently eat into the cap.

The cap defaults to 500 tokens and is configurable via
`Settings.NARRATIVE_CHUNK_TOKEN_CAP`.

#### Scenario: Section under the cap
- **WHEN** a whole narrative section fits within the cap
- **THEN** it becomes a single chunk and is not subdivided

#### Scenario: Bullet over the cap
- **WHEN** a top-level bullet with its children exceeds the cap
- **THEN** chunking descends to its child bullets and repeats the rule
- **AND** `metadata.bullet_path` records the breadcrumb of labels down to the chunk

#### Scenario: Leaf with no finer structure
- **WHEN** a unit exceeds the cap and has no further bullet level to descend into
- **THEN** it is split on sentence boundaries as a last resort
- **AND** a single run-on clause with no sentence punctuation is split on whole words

#### Scenario: Unión antes de la medición
- **WHEN** una unidad con enunciado colgado y su continuación juntas entran bajo el techo
- **THEN** se miden como una sola unidad y producen un solo chunk

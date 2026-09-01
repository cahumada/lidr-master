# document-chunking Delta Specification

## ADDED Requirements

### Requirement: Una unidad que deja el enunciado colgado NO DEBE emitirse sola
Una unidad narrativa cuyo texto termina en `,` o en `:` no cerró su enunciado:
continúa en la unidad siguiente. Emitirla sola produce dos chunks incompletos y,
cuando el enunciado es un condicional, algo peor que incompleto — la rama else
recuperada sin el conector que la marca como contraria se lee como la rama then
e invierte la regla de negocio.

El discriminador es **gramatical, no de largo**. `No aplica.` y `A petición del
usuario.` son cortas pero cierran su oración, y quedan intactas; `· De la tabla
de Situación impositiva del Cliente se obtiene:` es larga y no cierra nada. Los
marcadores de énfasis del export se sacan antes de mirar el último carácter: el
corpus escribe `### o _La información se obtiene de:_`, con los dos puntos
adentro de la itálica.

La unión avanza hasta que una unidad cierra el enunciado, y NO DEBE cruzar el
borde de la sección: dos secciones distintas no se continúan una a la otra.

Lo que esta regla reconstruye es el ENUNCIADO, no la lista ni el condicional
completo. Un lead-in seguido de tres ítems se une con el primero, porque ese ya
cierra la oración; una condición `§Si <cond>.` que cierra con punto no se pega a
sus ramas. Recuperar el bloque entero exigiría la jerarquía de glifos que el
corpus no lleva de forma confiable — ver `design.md` del cambio y su medición de
78,8%.

#### Scenario: Conector que separa las dos ramas de un condicional
- **WHEN** una sección contiene `·<rama then>`, `De lo contrario,` y
  `·<rama else>` como unidades consecutivas
- **THEN** `De lo contrario,` y la rama else quedan en el mismo chunk
- **AND** el conector no se emite nunca como chunk propio

#### Scenario: Lead-in seguido de lo que cierra su enunciado
- **WHEN** una unidad termina en `:` y la siguiente cierra la oración
- **THEN** las dos quedan en el mismo chunk
- **AND** un segundo ítem hermano, que ya cierra su propia oración, queda como
  chunk propio

#### Scenario: Respuesta corta que sí cierra su oración
- **WHEN** el contenido de una unidad es `No aplica.` o `A petición del usuario.`
- **THEN** se emite como su propio chunk, sin unirse a nada

#### Scenario: Enunciado colgado al final de la sección
- **WHEN** la última unidad de una sección deja el enunciado colgado
- **THEN** se emite tal cual, porque no hay unidad siguiente en esa sección
- **AND** no lleva `continues_into`, porque no hay a qué apuntar

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

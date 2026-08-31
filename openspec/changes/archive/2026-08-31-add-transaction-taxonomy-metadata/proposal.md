## Why

Se incorporó conocimiento de dominio sobre la taxonomía de navegación de
VisualTIME (`openspec/domain/visualtime-navigation-taxonomy.md`). Contrastarlo
contra el corpus y contra el pipeline actual destapó un **defecto real de
atribución** y dos huecos de metadata que limitan el retrieval.

**El defecto (medido sobre los 2169 archivos / 67.121 chunks, no inferido):**
el chunker asume 1 archivo = 1 transacción.

| Categoría | Archivos | Chunks |
|---|---|---|
| Multi-transacción (≥2 códigos en un archivo) | 72 (3,3%) | 3484 (5,2%) |
| Id mal asignado (el real ≠ el asignado) | 43 (2,0%) | 2143 (3,2%) |
| Índice/capítulo troceado como contenido | 60 (2,8%) | 2132 (3,2%) |

No es la mayoría del corpus, pero un chunk mal atribuido es una regla de
negocio de seguros contestada bajo la transacción incorrecta — y el error es
sistemático, no ruido aleatorio: la forma dominante es `<CODIGO>` +
`<CODIGO>_k`, la transacción de solicitud de clave acompañando a su principal
(`CP002`+`CP002_k`, `OP008`+`OP008_k`, `BC005`+`BC005_k`).

Casos concretos: `accounting_cpl500.md` lleva id real `CPL500` pero se le
asigna `ACCOUNTING_CPL500` (151 chunks), porque el nombre de archivo trae el
módulo como prefijo; `btc001_1.md` recibe `BTC001_1`, que **no es un código de
transacción real** sino un artefacto del nombre.

**Causa raíz encontrada:** `DOCUMENT_ID_PATTERN`
(`\(([A-Z]{2,4}\d{3}[a-z]?)\)`) no matchea `(BC005_k)`, `(VI7501_A)`, `(MENU)`
ni `(CA13-1)` — el guion bajo no está en el patrón y exige tres dígitos. Por eso
los ids con sufijo `_k` se pierden y caen al fallback. A esto se suma que la
búsqueda se limita al texto previo al primer `## ` del **archivo**, cuando en
la mayoría de estos documentos el bloque de id vive más abajo.

**Nota de honestidad:** una primera medición arrojó "96,2% de archivos resuelven
el id por fallback". Ese número es real pero engañoso: el 82% de los archivos no
tiene bloque de id, y ahí el fallback es correcto. El defecto son los 43 donde
el id existe y se asigna otro.

**Hueco 1 — documentos índice.** `policies/ca001a.md` es un nodo capítulo: 31
enlaces a sus hijos, sin `Campos` ni `Validaciones` propios. Hoy produce 5
chunks tratados como contenido. Son chunks de bajo valor que compiten en el
retrieval con contenido real, y su valor verdadero (las relaciones padre-hijo)
se pierde.

**Hueco 2 — sin taxonomía en la metadata.** Los chunks no llevan módulo,
submódulo ni tipo de transacción. Sin eso no se puede filtrar un retrieval por
módulo ("¿qué valida Cobranzas?") ni aplicar plantillas de parseo por tipo, que
es lo que la sección 6 del documento de dominio habilita.

## What Changes

- **Nueva capability `transaction-taxonomy`**: clasificación del tipo de
  transacción por patrón de código, y resolución del breadcrumb
  Módulo → Submódulo → Transacción a partir de un export de la tabla `WINDOWS`.
- **`document-chunking` pasa de 1 archivo = 1 documento a 1 archivo = N
  transacciones**: se detectan los bloques H1 con su propio bloque de id y cada
  chunk se atribuye a la transacción a la que realmente pertenece.
- **Detección de documento índice/capítulo**: se clasifica como tal y no se
  trocea como contenido; sus relaciones padre-hijo quedan disponibles como dato.
- **El código autoritativo se toma del contenido**, no del nombre de archivo;
  el nombre queda solo como fallback.
- **`ChunkMetadata` crece** con el tipo de transacción y el breadcrumb, para
  que el retrieval pueda filtrar por ellos.

## Capabilities

### Capabilities nuevas

- `transaction-taxonomy`: clasificar un código de transacción por tipo y
  ubicarlo en el árbol de navegación, con la distinción nodo de menú vs. hoja
  ejecutable.

### Capabilities modificadas

- `document-chunking`: atribución por transacción en archivos
  multi-transacción, detección de documentos índice, y metadata de taxonomía
  en cada chunk.

## Impacto

- `app/generation/rag/chunking/functional_spec.py` — segmentación por bloques
  H1 + atribución de `document_id` por bloque.
- `app/generation/rag/taxonomy.py` (nuevo) — clasificación por patrón y
  resolución de breadcrumb.
- `app/generation/rag/schemas.py` — nuevos campos en `ChunkMetadata`;
  probablemente `DocumentKind` (`content` / `index`).
- `app/config.py` — ruta al export de `WINDOWS`.
- `scripts/chunk_corpus.py` — reportar tipo y documentos índice.
- `tests/generation/rag/` — fixtures nuevos: `bc005.md` (multi-transacción),
  `ca001a.md` (índice).
- `openspec/specs/document-chunking/spec.md` y
  `openspec/specs/transaction-taxonomy/spec.md` al archivar.

## Dependencia bloqueante

**El breadcrumb Módulo → Submódulo → Transacción no es implementable todavía.**
No existe ningún export de la tabla `WINDOWS` accesible al pipeline: se buscó
en el corpus y no hay datos del árbol (`general/general_menu.md` documenta la
transacción de menú, no sus filas). La distinción nodo/hoja de la sección 3 del
documento de dominio depende de los mismos datos.

Se necesita un export de `WINDOWS` (CSV o JSON con `SCODISPL`, `SCODMEN`,
`SDESCRIPT`) para las tareas del grupo 3. El resto del cambio —el defecto de
atribución, los documentos índice, y la clasificación por patrón de código— no
depende de eso y puede avanzar ya.

## Fuera de alcance

- **Plantillas de parseo por tipo de transacción** (sección 6 del documento de
  dominio). Este cambio deja el tipo *disponible* en la metadata; usarlo para
  elegir una plantilla de secciones por tipo es un cambio siguiente, con su
  propio proposal. Mezclarlo acá haría un cambio imposible de revisar.
- **Las fuentes técnicas en vivo por tipo** (sección 7). Están marcadas como
  hipótesis sin validar en el documento de dominio; no se construye sobre una
  hipótesis.

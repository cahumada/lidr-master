## Why

Un cliente va a entregar documentación actualizada. Hoy eso rompe en silencio:

- `chunk_id` es `{document_id}::{sección}::{índice}` — la versión nueva genera
  **los mismos ids**, así que reingestar pisa o duplica según cómo esté armado
  el store.
- Ningún campo dice de qué versión es un chunk, ni cuál está vigente.
- Si una sección se corre de lugar, los índices se desplazan:
  `CA014::validaciones::7` puede pasar a apuntar a otra regla. El id es estable
  en formato pero **no en significado**.

Y el proyecto es multi-cliente: `corpus_schema.json` declara
`deployment_mode: "saas"` con `tenant_id`. Dos clientes pueden estar en
versiones distintas del mismo documento.

**El momento es ahora, antes de la capa de embeddings.** Agregar estos campos
hoy cuesta 11 segundos de regenerar el corpus. Agregarlos después de embeber
66.634 chunks obliga a re-embeber todo, y peor: sin `content_hash` no hay forma
de saber qué ya estaba.

`corpus_schema.json` **ya diseñó esto** y no está implementado en nuestro
pipeline: `version_control` (`doc_version`, `source_revision`, `valid_from`),
`source.content_hash`, y `manifest.tenant_id`. La descripción del propio
`content_hash` dice el porqué: *"si el hash coincide entre corridas de ingesta,
el embedding existente se reutiliza sin regenerar, reduciendo costo"*.

## What Changes

- **`content_hash` en dos niveles**: por documento (SHA-256 del contenido
  normalizado de su bloque) y por chunk (SHA-256 del `text` que se embebe).
  El de chunk es el que habilita reutilizar un embedding.
- **Identidad de versión**: `tenant_id` y `doc_version` en la metadata de cada
  chunk (es lo que el vector store filtra), más `source_revision` y
  `valid_from` por documento.
- **Manifiesto del corpus**: `data/chunks/manifest.json` con `corpus_id`,
  `tenant_id`, `doc_version`, `generated_at` y conteos — la declaración
  autoritativa de qué corrida produjo este corpus.
- **Clave compuesta declarada**: la identidad física de un chunk pasa a ser
  `(tenant_id, doc_version, chunk_id)`. `chunk_id` se mantiene estable entre
  versiones como *localizador*; `content_hash` es la identidad del *contenido*.
- **Flags en el batch**: `--tenant` y `--doc-version`.

## Capabilities

### Capabilities modificadas

- `chunk-schema`: identidad de versión y hashes de contenido en el contrato.
- `corpus-batch-chunking`: el manifiesto como artefacto de salida.

## Impact

- `app/generation/rag/schemas.py` — campos nuevos + `CorpusManifest`.
- `app/generation/rag/chunking/functional_spec.py` — cálculo de hashes,
  estampado de tenant/versión.
- `app/config.py` — `TENANT_ID`, `DOC_VERSION`.
- `app/dependencies.py`, `scripts/chunk_corpus.py` — cableado y flags.
- `openspec/specs/{chunk-schema,corpus-batch-chunking}/spec.md`.

## Decisión tomada: multi-tenant, que subsume el reemplazo simple

De las tres opciones planteadas (A reemplazo, B temporal, C multi-tenant) se
implementa **C**, porque es lo que `deployment_mode: "saas"` ya implica, y
porque C subsume A: con `(tenant_id, doc_version)` en la clave, "reemplazar"
es escribir una versión nueva y dejar de consultar la vieja.

`valid_from` se incluye igual —es un campo que el schema ya tiene y no cuesta
nada— así la opción B (consultar *"¿qué decía CA014 en marzo?"*) queda
disponible sin migración posterior.

**Lo que este cambio NO hace:** decidir *cuál* versión está activa. Eso es
responsabilidad de la capa de store, que no existe todavía. Acá se generan los
datos que permiten esa decisión, no la decisión.

## Tensión resuelta: dónde vive el `tenant_id`

El brief de procesamiento dice explícitamente: *"La identidad del cliente va
solo en el `manifest`, nunca repetida por unidad."* Eso es correcto para un
archivo JSON, donde repetir el tenant 2250 veces es puro peso.

Pero un vector store filtra **por fila**: sin `tenant_id` en la metadata del
chunk no hay forma de aislar un cliente en una consulta.

**Resolución:** el manifiesto sigue siendo la declaración autoritativa (según
la regla del brief) y además se estampa `tenant_id`/`doc_version` en
`ChunkMetadata`, que es la fila del índice. Cada repetición sirve a un
consumidor distinto: el JSON declara, el índice filtra.

## Decisión que queda ABIERTA y no tomo por mi cuenta

Los marcadores `<DF009>` son **marcadores de personalización por cliente** —
así los describe `corpus_schema.json`, que pide eliminarlos en la
normalización. Nuestro chunker los **conserva** como referencias `footnote_tag`
(233 en el corpus).

Con multi-tenant esto deja de ser un detalle: esos marcadores son justamente la
señal de qué párrafo es específico de un cliente. Conservarlos puede ser una
ventaja (saber qué está personalizado) o un problema (texto de un cliente
indexado para otro).

No lo cambio en este cambio: es una decisión de producto, no de
implementación, y merece su propio proposal con la evidencia de qué documentos
los llevan. El comportamiento actual queda documentado tal como es.

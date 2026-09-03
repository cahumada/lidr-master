## Why

A futuro se van a incorporar otros tipos de documento —contratos, condiciones de
póliza— y **todavía no están definidos**. El pedido es que la opción quede
abierta sin definirla.

Eso choca con un principio del repo: *"una abstracción con una única
implementación es ruido"*. Las dos cosas conviven si se separa **dejar la puerta
abierta** de **construir la habitación**, y el criterio para separarlas es
dónde vive la decisión.

### Dos puertas cerradas, de costo muy distinto

| | dónde vive | costo de abrirla después |
|---|---|---|
| no hay `source_type` | **persistido**: clave única, 57.101 filas | migración + backfill + regenerar corpus |
| el chunker está fijo en la firma | solo código | mecánico |

Solo la primera es asimétrica. La segunda no se toca: no hay dato comprometido,
y una abstracción diseñada para un formato que nadie vio se diseña mal por
definición.

### Ningún campo actual puede hacer ese trabajo

`document_kind` (`content`/`index`), `chunk_type` (`table`/`narrative`) y
`transaction_type` discriminan **dentro** de una especificación funcional.
Ninguno puede decir *"esto es una especificación funcional y no un contrato"*.
`SearchFilters` tiene siete campos y todos son internos al formato.

### Lo que este cambio NO arregla

Empecé a argumentarlo por seguridad ante colisiones y **la premisa era falsa**.
El `content_hash` cubre el header contextual `[Documento: CA014 - <título>]`, así
que dos documentos no pueden colisionar. Medido sobre el corpus
[VERIFICADO-CORPUS]: **3.017 hashes se repiten y 0 cruzan `document_id`**.

Las razones que quedan en pie son dos, y son más chicas pero reales:

1. **Un corpus mixto no se podría filtrar por clase de fuente.** Es la razón
   principal.
2. **`document_id` se vuelve ambiguo entre tipos.** Un contrato numerado `CA014`
   y una especificación `CA014` serían dos cosas distintas con el mismo id, y el
   camino exacto (`document_id IN (...)`) devolvería los dos.

Y como seguro: un tipo de fuente futuro que no lleve un header con su id sí
podría colisionar, y ahí la clave única lo previene.

## What Changes

- `ChunkMetadata.source_type`, con default `functional_spec`.
- `chunks.source_type`, y **dentro de la clave única**:
  `(tenant_id, doc_version, source_type, content_hash)`. Es identidad, no
  metadata, así que un conflicto NO la reescribe.
- `SearchFilters.source_type`, con `None` = todas.
- `FunctionalSpecChunker` lo estampa **explícito** aunque el modelo tenga ese
  default: el default sería el valor equivocado para un chunker futuro de otro
  formato, y un valor mal puesto en silencio dentro de la identidad de la fila es
  peor que uno faltante.
- Un `str` y no un `Literal`: un enum cerrado habría que editarlo para agregar
  el segundo tipo, y ese tipo no está definido.

**Deliberadamente afuera:** la clase abstracta `Chunker`, el ruteo por tipo en
el endpoint, y la tabla de chunks por tipo de fuente del curso.

## Impact

- Migración `62457660a177`. El `server_default` rellenó las 57.101 filas
  existentes sin backfill aparte.
- Corpus regenerado: 62.228 chunks, todos `functional_spec`.
- **Re-embedding: 0 tokens, 0 llamadas.** Tercera vez que la propiedad se
  confirma: la metadata vive afuera del texto embebido, así que ningún
  `content_hash` cambia.
- Store recargado, filtro verificado: `functional_spec` → 5 hits, un tipo
  inexistente → 0.
- Sin dependencias nuevas.

# vector-store Delta Specification

## ADDED Requirements

### Requirement: Una fila DEBE identificarse por (tenant_id, doc_version, content_hash)
El `chunk_id` es un localizador que se corre cuando el corpus se regenera. Atar
la identidad de una fila a su posición hace que una recarga apunte filas a otro
texto sin ninguna señal — la misma razón por la que el sidecar de vectores ya se
indexa por hash.

#### Scenario: Clave única
- **WHEN** se crea el esquema
- **THEN** existe una restricción única sobre `(tenant_id, doc_version, content_hash)`

#### Scenario: Recarga sin cambios
- **WHEN** se corre la carga dos veces sobre el mismo corpus
- **THEN** la segunda no inserta ninguna fila
- **AND** no falla

#### Scenario: Recarga después de regenerar el corpus
- **WHEN** el corpus cambió y se vuelve a cargar
- **THEN** se insertan solo los `content_hash` que no estaban
- **AND** las filas cuyo hash no cambió quedan intactas

### Requirement: Cada fila DEBE llevar los campos por los que se filtra, en columnas
`ChunkMetadata` es un modelo de campos fijos y son los que la búsqueda va a
filtrar: cliente, versión, módulo, tipo de transacción, tipo de documento,
sección y campo. En columnas se indexan, el planner tiene estadísticas reales y
un nombre mal escrito es un error de SQL, no un filtro que silenciosamente no
matchea nada.

#### Scenario: Filtro por cliente y versión
- **WHEN** se busca con un `tenant_id` y un `doc_version`
- **THEN** ninguna fila de otro cliente o de otra versión aparece en el resultado

#### Scenario: Filtro estructural
- **WHEN** se busca restringiendo por `module_code` o por `transaction_type`
- **THEN** el resultado solo trae filas que cumplen esa restricción

### Requirement: El operator class del índice DEBE coincidir con el operador de la consulta
Si no coinciden, Postgres no falla: ignora el índice HNSW. Es una degradación
invisible, así que se verifica.

#### Scenario: El índice se usa cuando conviene
- **WHEN** se pide el plan de una búsqueda por similitud sin filtros selectivos
- **THEN** el plan usa `ix_chunks_embedding_hnsw`

#### Scenario: Distancia coseno
- **WHEN** se buscan los k vecinos de un vector
- **THEN** el orden es por distancia coseno ascendente
- **AND** se devuelven a lo sumo k filas

### Requirement: Una búsqueda con filtros DEBE devolver todos los k que existan
Este es el defecto más peligroso de HNSW y no se manifiesta como lentitud sino
como **resultados equivocados**: el índice recorre sus candidatos más cercanos y
recién después aplica el `WHERE`. Si el filtro descarta a todos los que el
índice visitó, la consulta devuelve **cero filas** aunque haya miles que
cumplen.

Medido sobre el corpus real: una búsqueda filtrada por
`transaction_type = 'query'` devolvió **0 filas mientras 7.461 cumplían el
filtro** [VERIFICADO-CORPUS]. La misma consulta con búsqueda exacta devolvía 10.

El escaneo iterativo de pgvector 0.8 (`hnsw.iterative_scan`) sigue recorriendo
el índice hasta juntar suficientes filas que pasen el filtro. Se configura
**en la conexión**, no en cada consulta: una consulta que se lo olvide vuelve con
resultados equivocados en silencio, y eso no puede depender de que quien la
escriba se acuerde.

`strict_order` y no `relaxed_order`: conserva el orden exacto por distancia, y
en la medición fue además más rápido (48 ms contra 57 ms).

#### Scenario: Filtro selectivo con resultados
- **WHEN** se busca con un filtro que cumplen miles de filas
- **THEN** se devuelven k resultados, no cero

#### Scenario: El orden se conserva
- **WHEN** se busca con filtros
- **THEN** los resultados vienen en orden ascendente de distancia

#### Scenario: La configuración vive en la conexión
- **WHEN** se abre una sesión, del stack sincrónico o del asincrónico
- **THEN** `hnsw.iterative_scan` ya está configurado sin que la consulta lo pida

#### Scenario: Un filtro que no cumple nadie
- **WHEN** se busca con un `tenant_id` que no existe
- **THEN** se devuelven cero resultados, y el escaneo está acotado

### Requirement: A lo sumo UNA versión puede estar activa por cliente, garantizado por la base
Una regla así sostenida solo por el código de la aplicación se rompe con dos
procesos concurrentes.

#### Scenario: Segunda activación rechazada
- **WHEN** un cliente ya tiene una versión activa y se intenta activar otra
- **THEN** la base rechaza la operación

#### Scenario: Varias versiones inactivas conviven
- **WHEN** un cliente tiene varias versiones cargadas y ninguna activa
- **THEN** todas coexisten sin conflicto

#### Scenario: Clientes distintos no se estorban
- **WHEN** dos clientes tienen cada uno una versión activa
- **THEN** ninguna de las dos entra en conflicto con la otra

### Requirement: El full-text DEBE configurarse en español
El corpus es español. Con el stemmer inglés `pólizas` y `póliza` no colapsan y
`de`/`la`/`el` no son stopwords: sería un índice que no encuentra.

`content_tsv` es una columna generada `STORED`, no un trigger ni un cálculo del
cargador: así no puede quedar desincronizada del texto.

#### Scenario: Stemming en español
- **WHEN** se inserta una fila cuyo texto dice `pólizas`
- **THEN** su `content_tsv` contiene el mismo lexema que el de una fila que dice `póliza`

#### Scenario: La columna se mantiene sola
- **WHEN** se inserta una fila sin poblar `content_tsv`
- **THEN** la columna queda poblada igual

### Requirement: La carga masiva NO DEBE pasar por el ORM
57.131 filas de 1536 floats por `session.add_all()` son minutos y mucha memoria
para un trabajo que `COPY` hace de una. El ORM define el esquema y responde las
consultas; mover el bulto es del driver.

#### Scenario: Carga por COPY
- **WHEN** se carga un módulo del corpus
- **THEN** las filas entran por `COPY` a una tabla temporal
- **AND** pasan a la definitiva con `ON CONFLICT DO NOTHING`

#### Scenario: El vector cargado es el del sidecar
- **WHEN** se carga un chunk cuyo `content_hash` tiene vector en el `.npy`
- **THEN** el vector persistido es igual al del sidecar

#### Scenario: Un chunk sin vector no se inventa
- **WHEN** un chunk del corpus no tiene fila en el sidecar
- **THEN** no se carga, y se reporta cuántos quedaron fuera

### Requirement: La suite NO DEBE exigir una base, y los tests que la exigen NO DEBEN mentir
pgvector no se puede emular: la distancia coseno, HNSW y el diccionario español
de `to_tsvector` son Postgres, y un doble en memoria testearía otra cosa. Pero
la suite corre en segundos sin nada instalado, y eso vale.

Los tests que necesitan base se marcan `integration` y se saltean cuando no hay
una alcanzable. Un test que se saltea en silencio es peor que no tenerlo.

#### Scenario: Sin base disponible
- **WHEN** se corre `pytest` sin una base alcanzable
- **THEN** los tests de integración se saltean con el motivo dicho
- **AND** el resto de la suite pasa

#### Scenario: Con base disponible
- **WHEN** se corre `pytest -m integration` contra una base con la extensión
- **THEN** los tests corren de verdad contra ella

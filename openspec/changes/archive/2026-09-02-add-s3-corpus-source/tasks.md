# Tareas

## 1. La abstracción

- [x] 1.1 `CorpusSource` como `Protocol`, con la superficie mínima que el
      chunking usa: `modules()`, `read(key)`, `name_of(key)`, `label()`. No un
      sistema de archivos.
- [x] 1.2 `LocalCorpusSource` sobre un `Path`: lo de hoy, sin red ni
      credenciales, que es lo que la mantiene como la fuente de los tests.
- [x] 1.3 `S3CorpusSource` sobre un bucket, con el cliente **inyectado** igual
      que en `OpenAIEmbedder` y `LLMReranker`. El módulo no importa `boto3`, así
      que se testea con un doble.
- [x] 1.4 `module_of()` e `is_excluded()` compartidos: el mismo criterio en las
      dos fuentes, y no dos reglas que se pueden desalinear.

## 2. Lo que S3 hace distinto, y hay que respetar

- [x] 2.1 **Paginado.** `list_objects_v2` devuelve 1.000 claves por página y el
      corpus tiene 2.169 documentos: sin paginar se perderían más de la mitad
      **en silencio**. Test con las 2.169 claves reales, que exige 3 páginas.
- [x] 2.2 Un listado truncado **sin** token de continuación es un error y no un
      resultado parcial: la respuesta se contradice, y devolver lo que hay sería
      devolver un corpus incompleto sin avisar.
- [x] 2.3 ~~El prefijo se normaliza.~~ **Quitado.** Lo había agregado para un
      caso que no llegó: el bucket espeja el filesystem, con las carpetas de
      módulo en la raíz, así que la clave ES la ruta relativa y el prefijo sería
      siempre vacío. Un setting que nadie mueve contradice el mismo principio
      que este cambio invocó para justificar la abstracción.
- [x] 2.4 Una clave sin módulo se reporta y se saltea. Adivinarle un módulo la
      atribuiría al equivocado.
- [x] 2.5 Un byte inválido se decodifica con `replace` y no aborta: un
      documento malo no puede tirar una corrida de 2.169. El chunker ya reporta
      lo que no pudo leer.
- [x] 2.6 `name_of()` devuelve el nombre de archivo y nunca la clave entera: de
      ahí sale el id cuando el documento no lo declara.

## 3. Cableado

- [x] 3.1 `chunk_corpus()` recibe una `CorpusSource` en lugar de una `root`.
- [x] 3.2 `ChunkStepResult.source` y `manifest.source_root` llevan de dónde
      salió el corpus: uno sin procedencia no se puede rastrear.
- [x] 3.3 `get_corpus_source()` en la raíz de composición. `CORPUS_BUCKET` es
      lo que decide y no un flag aparte: un nombre de bucket y una ruta son
      excluyentes por naturaleza.
- [x] 3.4 La CLI sigue tomando `--root` y arma una `LocalCorpusSource`.
- [x] 3.5 La guarda del endpoint acepta cualquiera de las dos fuentes.
- [x] 3.6 `boto3` como dependencia, justificada en el `proposal.md`: firmar
      SigV4 a mano es criptografía de autenticación hecha en casa.
- [x] 3.7 `S3_REGION` vacía. La había puesto en `"auto"`, que es la convención
      de Cloudflare R2 y **una adivinanza para Railway**. Verificado: boto3 no
      necesita región con un endpoint custom, usa `us-east-1` solo. Y el valor
      **no es decorativo** — es la región con la que se firma SigV4, así que
      inventar uno puede romper la autenticación contra un servicio que la
      valide.
- [x] 3.8 Credenciales vacías caen a la cadena estándar de boto3 (variables
      `AWS_*`, `~/.aws/credentials`, rol de IAM). Verificado.

## 4. Verificación

- [x] 4.1 17 tests de las dos fuentes, sin red.
- [x] 4.2 **Documentos reales por la interfaz del bucket**: 60 archivos de
      `policies` y `claims` servidos por un cliente falso dieron **3.688
      chunks**, exactamente los mismos que desde disco. La abstracción no cambia
      el comportamiento.
- [x] 4.3 La CLI corrida completa: 2.169 archivos → 62.228 chunks, los mismos
      números de siempre.
- [x] 4.4 `embed_corpus --dry-run` reporta 0 para embeber y 57.131 reusadas: los
      `content_hash` no se movieron, así que el store sigue coherente y no hace
      falta recargarlo.
- [x] 4.5 `pytest` (482), `pytest -m integration`, `ruff check .` y
      `validate_specs` en verde.
- [x] 4.6 Promover el delta y archivar.

## 5. Lo que queda anotado y NO se hizo

- [ ] 5.1 **Los artefactos generados siguen siendo locales.** El corpus troceado
      son 86 MB y el sidecar 351 MB, y en un contenedor sin volumen se pierden en
      cada deploy. Re-trocear son 13 s y re-embeber **US$ 0,10** por 4.751.041
      tokens, así que no es caro — son ~446 lotes contra la API cada vez que el
      contenedor arranca de cero.
- [ ] 5.2 **El sidecar podría no ser necesario.** `embedding` está en
      `COPY_COLUMNS` pero **no** en `_METADATA_COLUMNS`, así que en un conflicto
      nunca se reescribe: para un hash que ya está en Postgres, el vector no hace
      falta porque la base ya lo tiene.

      No lo implementé de apuro porque tiene un modo de falla peligroso:
      `embedding` es `NOT NULL`, así que una fila que resulta ser nueva y llega
      sin vector real necesitaría un placeholder, y un vector en cero insertado
      por error se indexa donde nada matchea nunca — el fallo silencioso que la
      capa de embeddings rechaza a propósito. Requiere consultar antes qué
      hashes existen y tratar distinto los dos casos.

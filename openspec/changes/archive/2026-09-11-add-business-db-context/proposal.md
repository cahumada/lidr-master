## Why

El servicio responde con **una sola de las dos autoridades que tiene**. El corpus
funcional manda sobre la intención —para qué sirve una transacción, qué valida—
y la base de VisualTIME manda sobre **qué existe hoy**
([visualtime-database-metadata.md §10](../../domain/visualtime-database-metadata.md)).
De las dos, a la respuesta llega solo la primera.

El mirror está cargado y casi entero sin usar. Hoy el servicio lee
`visualtime.business_data` para exactamente una cosa —las filas de `WINDOWS`, para
armar el árbol de navegación— y no lee `visualtime.business_tables` en absoluto.
Lo que queda afuera está medido:

| | |
|---|---:|
| tablas con descripción de negocio escrita por humanos | **1.883 de 2.411 (78%)** |
| columnas con descripción | **24.556 de 33.486 (73%)** |
| filas de contenido cargadas en `business_data` | **201.751**, de 753 tablas |
| transacciones ejecutables activas **sin documento funcional** | **~655** |

Ese último número es el que duele. Para esas transacciones el comentario de la
columna en Oracle **es la única documentación que existe** (§3), y hoy el motor
las recupera del corpus —donde no están— y responde sin nada. Y para las que sí
tienen documento, *"¿qué valores admite este campo?"* es una pregunta cuya
respuesta vive en las filas de una `TABLE<n>`, no en el markdown: el documento
dice que el campo se carga de una tabla genérica, y ahí se corta.

La precondición ya aterrizó. `add-extraction-run-selection` dejó **una sola
respuesta** a "¿de qué corrida hablamos?", resuelta por request y con su origen
declarado. Sin eso, leer tres tablas más multiplicaba por tres el problema de
responder desde una corrida que ya nadie eligió — que es exactamente el defecto
que ese change sacó.

## What Changes

- **El ancla son los códigos de los hits.** El `document_id` de cada hit que entró
  al prompt (`CA014`, `MA0007`) resuelve contra `WINDOWS` de la corrida activa.
  Sin reconocimiento de entidades sobre la pregunta y sin una segunda pasada de
  LLM: el ancla es un dato declarado, no una inferencia.
- **La tabla que mantiene la transacción, solo para el tipo 10.** `NG_IDENTI`
  → `TABLE<n>`. La medición es tajante (§7.1): de 529 pares de tipo 10 que
  resuelven a una tabla existente **coinciden 440 (83%)**; de los 11 pares de
  otros tipos **coinciden 0**. Así que la arista se carga para el tipo 10 y solo
  para el tipo 10, y un `NG_IDENTI` en otro tipo se **ignora y se cuenta**, nunca
  se usa en silencio.
- **El diccionario, desde `business_tables`**: la descripción de la tabla y las de
  sus columnas. Es prosa de negocio, no DDL.
- **Las filas, desde `business_data`, filtradas por vigencia** (§4.4). El
  mecanismo **se lee de la propia tabla** —qué columnas declara— y nunca de una
  lista hardcodeada: `SSTATREGT` sola, período completo, los dos, o **ninguno**.
  Una tabla con media pareja (`DEFFECDATE` sin `DNULLDATE`, o al revés) **no tiene
  mecanismo declarado**: no se filtra, y el bloque lo dice. La fecha de referencia
  es el `created_at_utc` de la corrida activa, parametrizable — nunca `now()`
  (§4.3).
- **El bloque dice si se trajo todo o quedó algo afuera.** Es el requisito que
  ordena el diseño: cada código anclado termina en un resultado de un vocabulario
  **cerrado** (no está en la corrida, no declara tabla, la tabla no está en el
  diccionario, la tabla no está cargada, se recortó por presupuesto, …), y el
  bloque cierra con *qué no se pudo traer y por qué*. Un `complete: false` que no
  nombre la causa no sirve, y un bloque que calle lo que falta le hace afirmar al
  modelo sobre un catálogo incompleto que lo vio entero.
- **Un bloque propio en el prompt, versión `v3`.** Va separado de la evidencia y
  rotulado como otra autoridad: cuando la base y el documento difieren **no hay un
  error a resolver, hay un hallazgo a reportar** (§10), y meterlo adentro del
  bloque del hit mezclaría las dos. `v1` y `v2` siguen renderizando byte a byte
  para una corrida sin este bloque, como ya se hizo con la memoria.
- **Se cobra adentro de `ANSWER_MAX_CONTEXT_TOKENS`, y se ajusta último.** Después
  de la evidencia y después de la memoria. Recorta desde la cola, por filas
  enteras, y lo recortado se cuenta.

Fuera de alcance, y cada uno con su motivo:

- **`business_dependencies`** (documento → rutina → tablas, §5.3). Estaba en el
  enunciado y se difiere a propósito: los 1.622 pares necesitan la guarda de largo
  4 y el contraste contra `transaction_type` (§13.6) antes de poder viajar como
  hecho y no como indicio (§5.4). Es el change siguiente, no un olvido.
- **Las tablas nombradas en el texto del chunk** (563 de 2.411, §5.2). Tiene hueco
  de medición abierto: el token de 4+ caracteres hace que `TRACE` o `LEVELS`
  figuren por ser palabras corrientes.
- **Reconocimiento de entidades sobre la pregunta.** Una tabla que ningún hit
  ancla no entra. Cubrir eso es lo que habilita responder sobre las ~655
  transacciones sin documento, y es un change propio.
- **Resolver la precedencia entre los dos mecanismos de vigencia** en las 38
  tablas que tienen ambos (§13.3). Acá se **mide y se reporta** la discrepancia;
  decidir cuál gana necesita ese conteo primero.
- **La pantalla de consola.**

## Capabilities

### New Capabilities

- `business-db-context`: qué trae el servicio de la base fuente para una respuesta,
  desde qué corrida, con qué criterio de vigencia, y cómo declara lo que no pudo
  traer.

### Modified Capabilities

- `answer-generation`: el prompt gana una versión `v3` con el bloque de la base,
  subordinado a las reglas de anclaje y rotulado como otra autoridad; y el
  presupuesto de contexto pasa a repartirse entre tres bloques con un orden fijo.

## Impact

- `ai-service/app/generation/rag/business_db/` — nuevo paquete: `reader.py` (las
  consultas al mirror), `validity.py` (el predicado de vigencia por tabla),
  `render.py` (el bloque y su presupuesto), `models.py` (los tipos y el vocabulario
  de completitud).
- `ai-service/app/generation/rag/navigation.py` — el árbol gana `NG_IDENTI`, en la
  estructura en memoria y **no** en `NavigationLocation`: ese modelo viaja adentro
  de los chunks y agregarle un campo cambiaría la metadata del corpus.
- `ai-service/app/generation/rag/prompt_builder.py` — `v3` y el orden de ajuste.
- `ai-service/app/foundation/prompts/answer/v3/{system,user}.j2` — nuevos.
- `ai-service/app/generation/rag/answer.py` — el camino directo.
- `ai-service/app/domain/graph/agents/answer_synthesizer.py` — el camino agéntico,
  con la corrida que ya viaja en el estado.
- `ai-service/app/dependencies.py` — el resolver cacheado por corrida, al lado de
  `resolve_navigation_tree`.
- `ai-service/app/generation/rag/schemas.py` — `BusinessDbContext` y su campo en
  `AnswerResponse`.
- `ai-service/app/config.py`, `ai-service/.env.example` — techo, topes y la fecha
  de referencia.
- `ai-service/tests/generation/rag/business_db/`, `tests/api/`, `tests/generation/rag/` — tests.

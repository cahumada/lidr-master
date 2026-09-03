# corpus-rebuild Specification

## Purpose

Correr el pipeline del corpus —trocear, embeber, cargar— sin una terminal y sin
este repo clonado, para que apuntar el servicio a otra base sea cambiar una
variable y llamar un endpoint.

## Requirements

### Requirement: La orquestación DEBE vivir en un solo lugar
El endpoint y los scripts corren la misma secuencia. Dos implementaciones de lo
mismo divergen, y la que se rompe en silencio es la que nadie corre a mano.

El corte es: el pipeline dice qué hacer y devuelve un resultado estructurado;
los scripts lo cuentan a una consola; el endpoint lo cuenta a una fila de job.

#### Scenario: Un paso escribe su registro autoritativo una sola vez
- **WHEN** el paso de embeddings corre, por script o por endpoint
- **THEN** el manifiesto del sidecar se escribe igual, porque lo escribe el
  pipeline y no quien lo invoca

#### Scenario: Una librería lanza y una CLI traduce
- **WHEN** el pipeline no encuentra el corpus
- **THEN** lanza una excepción
- **AND** el script la convierte en un renglón por stderr y un código de salida
  1, no en un traceback

### Requirement: El rebuild NO DEBE bloquear el request
Medido: trocear son 12,5 s y cargar 141 s contra localhost, y embeber puede ser
horas si cambió el texto del corpus.

#### Scenario: Se devuelve un id y no un resultado
- **WHEN** se llama `POST /corpus/rebuild`
- **THEN** se responde 202 con el id del trabajo
- **AND** el trabajo corre en background

#### Scenario: El estado se puede consultar
- **WHEN** se consulta `GET /corpus/jobs/{id}`
- **THEN** se devuelve el estado, el paso actual, lo que produjo cada paso y la
  última línea de progreso

#### Scenario: El estado sobrevive al proceso
- **WHEN** el proceso reinicia con un trabajo a medio hacer
- **THEN** su fila sigue ahí, porque el estado vive en Postgres y no en memoria

#### Scenario: Un fallo queda registrado y no clavado
- **WHEN** un paso lanza una excepción
- **THEN** el trabajo queda como fallido con el mensaje del error
- **AND** nunca se queda en `running`, que bloquearía todos los rebuilds
  siguientes

### Requirement: Los pasos SE DEBEN correr en la única secuencia que funciona
Embeber un corpus que todavía no se troceó no es una preferencia, es un error.
El orden en que llegan los pasos no importa.

#### Scenario: Se reordenan
- **WHEN** se piden los pasos en cualquier orden
- **THEN** corren como reset, trocear, embeber, cargar

#### Scenario: Un paso desconocido no llega al runner
- **WHEN** se pide un paso que no existe
- **THEN** se descarta

### Requirement: A LO SUMO UN trabajo DEBE poder estar corriendo
Dos rebuilds escriben el mismo directorio de corpus y la misma tabla. Pasó: dos
corridas se solaparon y se trabaron entre sí, una borrando 57.101 filas y la
otra copiando sobre ellas.

La garantía es **de la base**. El chequeo que hace la aplicación existe para dar
un buen mensaje de error, y chequear-y-después-insertar es una carrera que dos
procesos pierden.

#### Scenario: Un segundo rebuild se rechaza
- **WHEN** se pide un rebuild con otro corriendo
- **THEN** se responde 409 nombrando el trabajo en curso

#### Scenario: La base se niega igual
- **WHEN** dos procesos insertan un trabajo `running` sin chequear antes
- **THEN** el segundo insert falla por el índice único parcial

#### Scenario: Terminado uno, entra el siguiente
- **WHEN** el trabajo en curso termina
- **THEN** un rebuild nuevo se acepta

### Requirement: Un paso destructivo NO DEBE viajar como un booleano
`reset` borra todas las filas del corpus. Un `reset=true` suelto en un historial
de shell no debería vaciar una base.

#### Scenario: Sin confirmación explícita se rechaza
- **WHEN** se pide `reset` sin `confirm_tenant_id` y `confirm_doc_version`
- **THEN** se responde 400

#### Scenario: Confirmando otro corpus se rechaza
- **WHEN** la confirmación no coincide con el corpus configurado
- **THEN** se responde 400

#### Scenario: El borrado tiene alcance de un corpus
- **WHEN** el reset corre
- **THEN** borra las filas de ese `(tenant_id, doc_version)` y nunca la tabla
  entera, que se llevaría los corpus de otros clientes

### Requirement: La raíz del corpus DEBE ser configuración y no un parámetro
Aceptar una ruta arbitraria por HTTP es una lectura de disco arbitraria de quien
pueda llamar al endpoint. La CLI sí toma `--root`, porque ahí quien llama ya
tiene el disco.

#### Scenario: Trocear sin raíz configurada se rechaza
- **WHEN** se pide el paso de trocear y `CORPUS_ROOT` no está configurada
- **THEN** se responde 409 diciendo cómo cargar el corpus que ya está en disco

#### Scenario: Cargar sin raíz configurada se permite
- **WHEN** se pide solo cargar
- **THEN** corre, porque cargar no lee ningún documento fuente

### Requirement: La fuente de los documentos DEBE ser intercambiable
Los documentos pueden estar en un directorio local o en un bucket
S3-compatible. El chunking necesita dos cosas de una fuente y no un sistema de
archivos: los documentos agrupados por módulo, y el texto de uno.

Esta abstracción entra ahora y no antes porque **entró la segunda fuente**. La
regla del proyecto —«una abstracción con una única implementación es ruido, se
agrega cuando entre la segunda estrategia»— se cumple, no se elude.

#### Scenario: Un directorio local
- **WHEN** la fuente es un directorio
- **THEN** los documentos se agrupan por su directorio de primer nivel

#### Scenario: Un bucket S3-compatible
- **WHEN** la fuente es un bucket
- **THEN** los documentos se agrupan por el primer segmento de su clave, porque
  S3 no tiene directorios y la pertenencia a un módulo es un prefijo

#### Scenario: Las dos fuentes producen lo mismo
- **WHEN** el mismo conjunto de documentos se trocea desde un directorio y
  desde un bucket
- **THEN** se producen los mismos chunks, **en el mismo orden**

#### Scenario: El orden no depende del sistema operativo
- **WHEN** se lista un directorio con nombres que difieren en mayúsculas
- **THEN** el orden es el mismo en Windows y en Linux, porque se ordena por la
  clave relativa y no por el `Path` —que en Windows compara sin distinguir
  mayúsculas y reordenaría el corpus en silencio al desplegar

#### Scenario: Una subcarpeta pertenece a su módulo de primer nivel
- **WHEN** un documento está en `accounting/reports/cpl500.md`
- **THEN** pertenece al módulo `accounting` y no a `accounting/reports`

#### Scenario: El corpus declara de dónde salió
- **WHEN** se escribe el manifiesto
- **THEN** lleva la fuente, porque un corpus sin procedencia no se puede
  rastrear

#### Scenario: La fuente se elige por la configuración
- **WHEN** hay un bucket configurado
- **THEN** se usa el bucket
- **AND** si no, el directorio local

### Requirement: Un listado de bucket DEBE leerse completo o fallar
`list_objects_v2` devuelve como máximo 1.000 claves por página y el corpus tiene
2.169 documentos. Un listado a medias no es un corpus más chico: es un corpus
al que le faltan reglas de negocio sin que nadie se enteró.

#### Scenario: Se pagina
- **WHEN** el bucket tiene más claves que una página
- **THEN** se piden todas las páginas

#### Scenario: Un listado truncado sin token es un error
- **WHEN** la respuesta dice que está truncada y no trae token de continuación
- **THEN** se levanta un error en lugar de devolver lo que llegó

### Requirement: Un documento ilegible NO DEBE abortar la corrida
Son 2.169 documentos de un export real. Uno con un byte inválido, o una clave
que el bucket no devuelve, se reporta y la corrida sigue.

#### Scenario: Un byte inválido
- **WHEN** un documento no decodifica como UTF-8
- **THEN** se decodifica reemplazando lo inválido y se trocea

#### Scenario: Una lectura que falla
- **WHEN** leer un documento lanza
- **THEN** se registra entre los archivos fallidos y la corrida sigue con el
  resto

#### Scenario: Una clave sin módulo
- **WHEN** una clave del bucket no tiene un segmento de módulo
- **THEN** se reporta y se saltea, en lugar de adivinarle uno

<!-- Promovido de: add-rebuild-endpoint -->
### Requirement: Los artefactos generados DEBEN vivir bajo su versión
El corpus troceado y el sidecar de vectores son de una versión concreta de la
documentación. Con rutas fijas, re-trocear una versión nueva **destruye los
artefactos de la anterior** en el lugar, y con ellos la posibilidad de recargarla
sin volver a pagar por embeberla.

Demostrado: de 384 chunks de un primer corpus, sobrevivieron **0** al trocear un
segundo encima.

El tenant NO va en la ruta: un proceso sirve exactamente un tenant
—`Settings.TENANT_ID` es un valor único leído en todos lados— así que un segmento
por tenant sería un nivel de directorio que nunca tiene hermanos.

#### Scenario: Dos versiones conviven
- **WHEN** se trocean dos versiones de la documentación
- **THEN** cada una queda en su propio directorio y ninguna pisa a la otra

#### Scenario: El nombre del directorio es usable
- **WHEN** un `doc_version` tiene espacios o puntos
- **THEN** el directorio lleva un nombre seguro para el filesystem

#### Scenario: Dos versiones parecidas no comparten directorio
- **WHEN** dos `doc_version` distintos producen el mismo slug
- **THEN** sus directorios siguen siendo distintos, porque el nombre lleva una
  huella del valor original

#### Scenario: El manifiesto tiene que coincidir con su directorio
- **WHEN** el manifiesto de un directorio declara otra versión que la que nombra
  al directorio
- **THEN** se levanta un error, porque cargar un corpus atribuyéndolo a otra
  versión no se ve después: las filas quedan con la versión equivocada y el
  prune de la versión real las borra

#### Scenario: El reporte queda con los artefactos
- **WHEN** un paso escribe su reporte legible
- **THEN** queda en el mismo directorio que los artefactos de esa versión, y no
  en la base

<!-- Promovido de: add-s3-corpus-source -->
<!-- Promovido de: add-versioned-artifacts -->

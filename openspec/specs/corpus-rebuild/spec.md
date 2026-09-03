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

<!-- Promovido de: add-rebuild-endpoint -->

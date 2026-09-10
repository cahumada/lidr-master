# web-console Delta Specification

## ADDED Requirements

### Requirement: El browser nunca llama al servicio IA directo
Toda llamada al servicio IA SHALL originarse en el servidor de
`business-backend/` (Route Handlers), usando una variable de entorno privada
para la URL. Ningún componente de cliente SHALL leer esa URL, y ninguna
respuesta al browser SHALL contenerla.

#### Scenario: el browser solo ve el origen de la app web
- **WHEN** un usuario ejecuta una búsqueda desde el browser
- **THEN** la request de red del browser tiene como destino una ruta de
  `business-backend/` (p. ej. `/api/search`)
- **AND** ni el bundle de cliente ni ninguna respuesta contienen la URL del
  servicio IA

### Requirement: Una sola capa habla HTTP con el servicio IA
El acceso HTTP al servicio IA SHALL estar confinado a `lib/ai-service/`: un
cliente base más un cliente por contexto (`search`, `documents`, `corpus`).
Ninguna pantalla ni Route Handler SHALL hacer `fetch` al servicio por su
cuenta, y los contextos NO SHALL importarse entre sí.

#### Scenario: agregar una llamada nueva
- **WHEN** una pantalla necesita un endpoint del servicio IA que todavía no se
  consume
- **THEN** el método nuevo se agrega al cliente del contexto que corresponde
- **AND** la pantalla lo consume a través de ese cliente, nunca con un `fetch`
  propio

### Requirement: La app web nunca llama a un proveedor de modelos
`business-backend/` SHALL obtener toda capacidad de IA del servicio IA. NO
SHALL contener credenciales de ningún proveedor de modelos, ni siquiera del
lado del servidor, ni llamar a un proveedor directamente.

#### Scenario: una funcionalidad nueva necesita un modelo
- **WHEN** una pantalla necesita algo que requiere una llamada a un LLM
- **THEN** esa llamada la hace el servicio IA detrás de un endpoint propio
- **AND** la app web solo consume ese endpoint

### Requirement: Las vistas renderizan objetos tipados
Las respuestas del servicio IA SHALL estar tipadas en TypeScript espejando los
schemas Pydantic del servicio. Ninguna pantalla SHALL renderizar JSON crudo ni
acceder a campos no declarados en esos tipos.

#### Scenario: el servicio agrega un campo
- **WHEN** el servicio IA agrega un campo a una respuesta
- **THEN** el tipo de `lib/ai-service/types.ts` se actualiza antes de que
  ninguna pantalla lo use

### Requirement: La consola se ve en claro y en oscuro, sin flash
Toda pantalla SHALL renderizarse legible en tema claro y en tema oscuro, con un
único juego de tokens de color: ninguna pantalla SHALL fijar un color literal
que no salga de esos tokens. Cuando el usuario no eligió tema, la consola SHALL
seguir la preferencia del sistema (`prefers-color-scheme`); cuando eligió, esa
elección SHALL persistir entre recargas y ganarle al sistema. El tema vigente
SHALL quedar aplicado antes del primer pintado, no después de hidratar.

#### Scenario: primera visita con el sistema en oscuro
- **WHEN** un usuario que nunca eligió tema abre la consola con su sistema
  operativo en modo oscuro
- **THEN** la primera pintura de la página ya es oscura
- **AND** no se ve un fondo claro intermedio

#### Scenario: la elección sobrevive la recarga
- **WHEN** el usuario cambia el tema con el conmutador y recarga la página
- **THEN** la página vuelve con el tema que eligió
- **AND** ese tema se mantiene aunque el sistema operativo pida el contrario

### Requirement: La pantalla de búsqueda expone la procedencia de cada resultado
La pantalla SHALL llamar a `GET /search` y renderizar, por cada resultado, su
`document_id`, `document_title`, `section`, `score` y las ramas (`branches`)
que lo encontraron. Cuando la descomposición está activa, SHALL mostrar las
`sub_queries` devueltas.

#### Scenario: resultado con procedencia completa
- **WHEN** una búsqueda devuelve al menos un resultado
- **THEN** cada resultado muestra su documento de origen, su sección y qué
  rama(s) de recuperación lo aportaron
- **AND** ningún resultado se muestra sin esa procedencia

#### Scenario: consulta compuesta con `split` activo
- **WHEN** el usuario deja activada la descomposición (default del endpoint)
- **THEN** la pantalla muestra las sub-preguntas en las que se dividió la
  consulta, tal como vienen en `SearchResponse.sub_queries`

### Requirement: Los filtros de módulo y tipo de ventana son de selección múltiple
La pantalla de búsqueda SHALL ofrecer `Módulo` y `Tipo de ventana` como
listados de selección múltiple, poblados desde `GET /api/search/facets` — no
desde una lista escrita a mano en la pantalla. `Módulo` SHALL tener "Todos"
seleccionado por default; `Tipo de ventana` SHALL tener "Cualquiera"
seleccionado por default. Seleccionar el default y seleccionar valores
puntuales SHALL ser mutuamente excluyente: elegir un valor puntual apaga el
default, y no dejar ningún valor puntual elegido vuelve al default.

#### Scenario: Estado inicial
- **WHEN** la pantalla de búsqueda carga
- **THEN** `Módulo` muestra "Todos" seleccionado y `Tipo de ventana` muestra
  "Cualquiera" seleccionado
- **AND** la búsqueda no manda `module_code` ni `window_type_name`

#### Scenario: Elegir varios módulos
- **WHEN** el usuario selecciona `CA` y `DF` en el listado de módulos
- **THEN** "Todos" queda deseleccionado
- **AND** la búsqueda manda `module_code=CA` y `module_code=DF`

#### Scenario: Deseleccionar todos los valores puntuales
- **WHEN** el usuario deselecciona el último módulo puntual que tenía elegido
- **THEN** el listado vuelve a mostrar "Todos" seleccionado
- **AND** la búsqueda deja de mandar `module_code`

### Requirement: La vista previa de ingesta no persiste
La pantalla de ingesta SHALL llamar a `POST /documents/ingest` o
`POST /documents/ingest-file` y mostrar los chunks y estadísticas devueltos. NO
SHALL ofrecer ninguna acción que persista ese resultado en el corpus.

#### Scenario: subir un documento
- **WHEN** el usuario sube un archivo `.md`
- **THEN** la pantalla muestra los chunks resultantes y sus estadísticas
- **AND** no aparece ninguna fila nueva en `chunks` como consecuencia

### Requirement: La reconstrucción de corpus repite el guard de `reset`
La pantalla SHALL mantener deshabilitado el envío de una reconstrucción con
`reset=true` hasta que el usuario confirme el `tenant_id` y `doc_version`
vigentes, obtenidos de una llamada de solo lectura al servicio — nunca de un
valor escrito en el código de la UI.

#### Scenario: intento de reset sin confirmar
- **WHEN** el usuario activa el reset pero no completa la confirmación
- **THEN** el botón de envío permanece deshabilitado
- **AND** no se emite ninguna llamada a `POST /corpus/rebuild`

#### Scenario: reset confirmado
- **WHEN** el usuario completa `tenant_id` y `doc_version` coincidiendo con los
  valores vigentes
- **THEN** la pantalla envía `POST /corpus/rebuild` con `reset=true` y sus
  campos de confirmación

### Requirement: Los errores del servicio se muestran con su significado
La app web SHALL distinguir los errores documentados del servicio y mostrarlos
con su significado, nunca como una falla genérica ni como una traza cruda. Un
409 de `POST /corpus/rebuild` SHALL presentarse como "hay una reconstrucción en
curso" con referencia al job existente.

#### Scenario: ya hay un job corriendo
- **WHEN** el usuario pide una reconstrucción y el servicio responde 409
- **THEN** la pantalla informa que ya hay una reconstrucción en curso y enlaza
  al job que la está ejecutando

#### Scenario: el servicio IA no responde
- **WHEN** el servicio IA está caído o devuelve 5xx
- **THEN** la pantalla muestra un mensaje que dice qué falló
- **AND** no expone una traza ni el detalle interno de la respuesta

### Requirement: El estado de un job de reconstrucción es visible sin terminal
Tras iniciar una reconstrucción, la pantalla SHALL sondear
`GET /corpus/jobs/{id}` y mostrar `current_step`, `progress`, `status` y
`error` cuando lo haya, hasta que el job termine o falle. La lista de jobs
recientes SHALL estar disponible desde `GET /corpus/jobs`.

#### Scenario: job en curso
- **WHEN** un job de reconstrucción está corriendo
- **THEN** la pantalla refleja su paso actual y su progreso sin que el usuario
  recargue la página

#### Scenario: job fallido
- **WHEN** un job termina con `status=failed`
- **THEN** la pantalla muestra el mensaje de `error` que devuelve la API

### Requirement: Cada proyecto se prueba y se despliega por separado
CI SHALL ejecutar los checks de un proyecto solo cuando cambien sus rutas, y el
despliegue de cada proyecto a su plataforma (Vercel para `business-backend/`,
Railway para `ai-service/`) SHALL dispararse solo por cambios en las rutas de
ese proyecto.

#### Scenario: cambio solo en la app web
- **WHEN** un commit a `main` toca únicamente archivos bajo `business-backend/`
- **THEN** el job de CI del servicio IA no se ejecuta
- **AND** Railway no produce un deploy nuevo

#### Scenario: cambio solo en el servicio IA
- **WHEN** un commit a `main` toca únicamente archivos bajo `ai-service/`
- **THEN** el job de CI de la app web no se ejecuta
- **AND** Vercel no produce un deploy nuevo

# service-authentication Specification

## Purpose

Qué exige el servicio para atenderte. La consola autentica **personas**; el
servicio autentica a **su cliente**: tiene uno solo legítimo —el BFF, que corre
en el servidor— y lo que necesita saber no es quién pregunta sino si quien llama
es su consola. Eso es un secreto compartido, no un modelo de usuarios.

Implementado en `app/config.py` (el setting y la regla de arranque),
`app/dependencies.py` (`require_service_token`) y `app/main.py` (la guarda a
nivel de router, con `/health` afuera).

Promovido de: `add-service-authentication`.

Verificado en producción el 2026-09-10: `/config` y `/search` devuelven 401 sin
header, `/health` sigue en 200.

## Requirements

### Requirement: El servicio DEBE exigir un token compartido para atender
El servicio se despliega con URL pública y su único cliente legítimo es el BFF
de la consola, que corre en el servidor. Lo que el servicio necesita saber no es
*quién* pregunta —eso lo autentica la consola— sino *si quien llama es su
consola*, y eso es un secreto compartido.

Todo endpoint SHALL exigir `Authorization: Bearer <token>` con el valor de
`SERVICE_TOKEN`, comparado en tiempo constante. La comprobación SHALL aplicarse
a nivel de router y no endpoint por endpoint: un endpoint nuevo tiene que quedar
cerrado sin que nadie se acuerde de cerrarlo.

Las **lecturas también se exigen**. No son gratis: `GET /search` llama al
embedder en cada consulta, `GET /config` revela el catálogo y los proveedores
configurados, y `GET /usage/summary` expone el consumo del tenant.

#### Scenario: Llamada sin token
- **WHEN** llega una request sin `Authorization` y hay un token configurado
- **THEN** el servicio responde 401 con `WWW-Authenticate: Bearer`
- **AND** el endpoint no ejecuta nada

#### Scenario: Llamada con el token correcto
- **WHEN** la request trae el token configurado
- **THEN** el endpoint responde como responde normalmente

#### Scenario: Una lectura tampoco es libre
- **WHEN** llega un `GET /search` sin token y hay un token configurado
- **THEN** responde 401
- **AND** no se llama al embedder

#### Scenario: Un endpoint nuevo nace cerrado
- **WHEN** se agrega un endpoint a un router protegido
- **THEN** exige el token sin ninguna anotación propia

### Requirement: El healthcheck DEBE quedar abierto
`/health` SHALL responder sin token. Es el healthcheck del despliegue: cerrarlo
haría que la plataforma marque el servicio como caído y lo reinicie en loop, que
es la peor forma posible de romper esto.

Es el único endpoint abierto, y no devuelve nada que sirva para reconocimiento.

#### Scenario: El healthcheck responde sin credenciales
- **WHEN** llega `GET /health` sin `Authorization` y hay un token configurado
- **THEN** responde 200

### Requirement: Sin token configurado el servicio DEBE quedar abierto y decirlo
Un token obligatorio en todos los entornos obligaría a configurarlo para correr
los tests, los evals y cualquier `curl` local, y alguien terminaría dejándolo
escrito en un `conftest`.

Con `SERVICE_TOKEN` vacío el servicio SHALL atender sin exigir nada y SHALL
registrar un warning al arrancar, con un nombre de evento buscable. Ese warning
es la única señal de que un entorno está abierto.

#### Scenario: Entorno de desarrollo sin token
- **WHEN** el servicio arranca con `SERVICE_TOKEN` vacío y `APP_ENV` distinto de
  `production`
- **THEN** arranca y atiende sin exigir el header
- **AND** deja un warning que dice que la autenticación está deshabilitada

### Requirement: En producción sin token el servicio NO DEBE arrancar
Una autenticación apagada por default que un despliegue se olvidó de configurar
es **peor** que no tenerla: queda abierta con aspecto de cerrada, y la
declaración de que no hay auth —que hoy existe— desaparece.

Con `APP_ENV=production` y `SERVICE_TOKEN` vacío, la validación de `Settings`
SHALL fallar nombrando la variable que falta, en lugar de arrancar abierto.

#### Scenario: Producción sin el secreto
- **WHEN** el servicio arranca con `APP_ENV=production` y sin `SERVICE_TOKEN`
- **THEN** la construcción de `Settings` falla
- **AND** el error nombra la variable que hay que cargar

### Requirement: El error NO DEBE decir por qué falló
Distinguir «faltaba el token» de «el token no coincide» solo le sirve a quien
está probando tokens. El 401 SHALL ser el mismo en los dos casos, y la
comparación SHALL ser en tiempo constante para no filtrar el largo.

#### Scenario: Token ausente y token incorrecto son indistinguibles
- **WHEN** una request llega sin header y otra con un token equivocado
- **THEN** las dos reciben la misma respuesta 401
- **AND** ninguna dice cuál de las dos cosas pasó

### Requirement: Esto cierra el acceso anónimo, NO el gasto ni la atribución
El token corta a quien no lo tiene. NO acota lo que puede hacer quien lo tiene:
`POST /answer` sigue sin tope de gasto, y el ledger de `llm-usage-accounting`
sigue atribuyendo cada llamada al portador del token —el BFF— y no a la persona
que preguntó, porque el servicio no tiene identidad de usuario.

Las dos cosas SHALL quedar declaradas, para que nadie lea «el servicio está
autenticado» y deduzca que además está acotado.

#### Scenario: El gasto sigue sin tope
- **WHEN** un cliente con el token válido llama `POST /answer` repetidamente
- **THEN** el servicio responde cada vez
- **AND** el ledger registra el consumo, que es registrar y no limitar

<!-- Promovido de: add-service-authentication -->

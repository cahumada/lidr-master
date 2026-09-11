# web-console Delta Specification

## ADDED Requirements

### Requirement: El administrador elige la corrida del mirror
La consola SHALL exponer `/business-db` al rol `administrador`
(módulo Configuración). La pantalla SHALL listar **todas** las
corridas de `GET /api/business-db/runs` (las que el servicio
devuelve, más nueva primero) y SHALL NOT ocultar las que no se
pueden activar. Cada fila SHALL mostrar al menos `run_id`, `env`,
`created_at_utc`, el `status` del extractor y las tres banderas de
carga. El control de activar SHALL estar habilitado solo cuando
`can_activate` es true y la fila no es la vigente. Activar SHALL
pedir confirmación y SHALL POST a
`/api/business-db/runs/{run_id}/activate` con `activated_by`
declarado desde la sesión de la consola cuando hay email o nombre;
si no hay, el campo viaja ausente. Un 409 o 404 SHALL mostrarse
con el `error` del BFF y SHALL NOT cambiar la vigencia en
pantalla como si hubiera alcanzado.

El encabezado SHALL decir cuál corrida está en vigor, su `origin`
(`selected` / `default` / `none`) y, cuando hay sello, si coincide
con la activa. Un desfasaje SHALL verse; SHALL NOT corregirse
solo.

Si `GET /business-db/runs` no existe o no responde, la página
SHALL renderizar igual, con lista vacía y el `error` del BFF, y
SHALL NOT inventar corridas.

El browser SHALL llamar solo a los Route Handlers same-origin.

#### Scenario: se ven las incompletas y no se eligen
- **WHEN** un administrador abre `/business-db` y el listado trae
  una corrida con `can_activate=false`
- **THEN** esa fila aparece con sus banderas de carga
- **AND** no tiene un control de activar habilitado

#### Scenario: solo una completa se puede activar
- **WHEN** el administrador confirma activar una corrida con
  `can_activate=true` que no es la vigente
- **THEN** la consola llama a
  `POST /api/business-db/runs/{run_id}/activate`
- **AND** si el servicio responde 200, esa corrida pasa a
  mostrarse como vigente con `origin=selected`

#### Scenario: el servicio rechaza una corrida sin datos
- **WHEN** el POST vuelve 409
- **THEN** la pantalla muestra el error del BFF
- **AND** la vigencia anterior sigue visible

#### Scenario: desfasaje del sello
- **WHEN** `stamp.matches_active` es false
- **THEN** el encabezado nombra la corrida del sello y la activa
- **AND** no dispara ningún activate por su cuenta

#### Scenario: servicio sin el endpoint
- **WHEN** `GET /business-db/runs` es 404 o el servicio no responde
- **THEN** `/business-db` igual renderiza
- **AND** un aviso lleva el `error` del BFF

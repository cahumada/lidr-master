# web-console Delta Specification

## ADDED Requirements

### Requirement: El administrador lee el agregado de tokens de chat del tenant
La consola SHALL exponer `/usage` al rol `administrador` (módulo
Configuración). La pantalla SHALL renderizar los totales de
`GET /api/usage/summary` (`total_calls`, `input_tokens`,
`output_tokens`, `total_tokens`) y una tabla `by_model`. Los
filtros opcionales `from`, `to`, `purpose` y `session_id` SHALL
reenviarse como query params sin una segunda capa de
validación. Al abrir la pantalla, `from` y `to` SHALL
prellenarse con el mes calendario en curso (America/Argentina/
Buenos_Aires) y la primera lectura SHALL pedir ese recorte. Un
rango invertido SHALL mostrar el 422 del servicio, no una tabla
vacía en silencio.

Un ledger vacío SHALL renderizar ceros y una frase explicativa,
no un error. Si el endpoint de arriba no existe o no responde,
la página SHALL degradar a ese estado vacío más el `error` del
BFF y SHALL NOT inventar totales desde la sesión del browser.

El browser SHALL llamar solo al Route Handler same-origin.

#### Scenario: el mes en curso es el recorte inicial
- **WHEN** un administrador abre `/usage` el 7 de septiembre
- **THEN** los filtros `from` y `to` muestran el 1 y el último
  día de septiembre
- **AND** la primera lectura pide ese rango, no el histórico
  entero

#### Scenario: ledger vacío
- **WHEN** un administrador abre `/usage` y el servicio
  devuelve ceros
- **THEN** las cards muestran 0
- **AND** la tabla se reemplaza por una frase que todavía no
  hay completions cobradas

#### Scenario: rango invertido se muestra, no se traga
- **WHEN** el administrador aplica un `from` posterior a `to`
- **THEN** la pantalla muestra el error del BFF que vino del 422
- **AND** los totales previos quedan visibles o las cards
  conservan la última lectura exitosa — SHALL NOT volverse un
  éxito falso en cero

#### Scenario: servicio sin el endpoint
- **WHEN** `GET /usage/summary` es 404 o el servicio no
  responde
- **THEN** `/usage` igual renderiza
- **AND** un aviso lleva el `error` del BFF

### Requirement: Un turno en vivo muestra el usage de la última completion
Cuando un turno agentico en vivo completa o pausa y el payload
trae `usage.reported=true`, el chat SHALL mostrar los tokens de
input, output y total de ese turno. Un turno cargado desde
`history` SHALL NOT mostrar cifras de tokens salvo que el
snapshot las traiga — la consola SHALL NOT escribir ceros que
se lean como una medición.

#### Scenario: turno sintetizado reporta usage
- **WHEN** el payload de un turno completado trae
  `usage.total_tokens=140` y `usage.reported=true`
- **THEN** ese turno del chat muestra 140 tokens en total

#### Scenario: turno reabierto no inventa usage
- **WHEN** el operador reabre una conversación desde `history`
- **THEN** esos turnos no muestran una línea de tokens

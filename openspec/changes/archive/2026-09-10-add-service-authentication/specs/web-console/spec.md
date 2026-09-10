# web-console Delta Specification

## MODIFIED Requirements

### Requirement: Una sola capa habla HTTP con el servicio IA
El acceso HTTP al servicio IA SHALL estar confinado a `lib/ai-service/`: un
cliente base más un cliente por contexto (`search`, `documents`, `corpus`).
Ninguna pantalla ni Route Handler SHALL hacer `fetch` al servicio por su
cuenta, y los contextos NO SHALL importarse entre sí.

Ese cliente base SHALL adjuntar el token de servicio en cada request, en el
único lugar donde se hace `fetch` contra el servicio. La variable SHALL vivir
del lado del servidor y **SHALL NOT** llevar el prefijo `NEXT_PUBLIC_`: ese
prefijo es exactamente el mecanismo que la expondría al browser. El módulo ya es
`server-only`, así que la garantía es estructural y no una convención — la misma
razón por la que `AI_SERVICE_URL` vive ahí.

Cuando la variable no está configurada, el cliente SHALL NOT mandar el header ni
inventar un valor: el servicio puede estar abierto a propósito en desarrollo.

#### Scenario: agregar una llamada nueva
- **WHEN** una pantalla necesita un endpoint del servicio IA que todavía no se
  consume
- **THEN** el método nuevo se agrega al cliente del contexto que corresponde
- **AND** la pantalla lo consume a través de ese cliente, nunca con un `fetch`
  propio

#### Scenario: el token viaja en toda llamada
- **WHEN** cualquier cliente de contexto llama al servicio
- **THEN** la request lleva el token, porque lo agrega el cliente base
- **AND** ninguna pantalla ni Route Handler lo maneja

#### Scenario: el token no puede llegar al browser
- **WHEN** se inspecciona el bundle de cliente y cualquier respuesta al browser
- **THEN** el token no aparece en ninguno de los dos

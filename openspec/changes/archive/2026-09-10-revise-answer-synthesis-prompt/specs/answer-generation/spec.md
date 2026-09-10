# answer-generation Delta Specification

## MODIFIED Requirements

### Requirement: El prompt DEBE instruir anclaje, síntesis, fuentes al final e insuficiencia
El system prompt dice cuatro cosas que el resto del sistema puede observar:
responder solo con el contexto recuperado; redactar una explicación continua
y no reenviar los bloques; no citar `[document_id · section]` en el cuerpo
y cerrar toda la respuesta con `Fuentes citadas:` y los `document_id`
usados; declarar la frase fija de insuficiencia cuando el contexto no
alcanza. Cada chunk entra al user prompt con su procedencia visible —para
que el modelo sepa qué códigos copiar al cierre—, no como texto pelado, y
el user prompt no le pide citar en el cuerpo.

Las cinco reglas siguen primero. Persona, guardrails de operador y el
bloque de memoria (cuando hay) se appendean después y se declaran
subordinados: no pueden pedir inventar, omitir el cierre de fuentes ni
salir del contexto.

#### Scenario: El contexto lleva procedencia
- **WHEN** se arma el prompt con un hit de `CA014` sección `Validaciones`
- **THEN** el bloque de contexto contiene `CA014` y `Validaciones` junto al
  texto del chunk

#### Scenario: El system prompt pide síntesis y fuentes al final
- **WHEN** se renderiza `answer/v1/system.j2`
- **THEN** el texto instruye responder solo con el contexto
- **AND** instruye no usar `[document_id · section]` en el cuerpo
- **AND** instruye cerrar con `Fuentes citadas:`
- **AND** instruye redactar una explicación y no reenviar los bloques
- **AND** instruye declarar insuficiencia cuando el contexto no alcanza

#### Scenario: El rol base cubre ambos perfiles y no es una persona
- **WHEN** se renderiza `answer/v1/system.j2` sin persona
- **THEN** el texto no se presenta como analista funcional
- **AND** nombra el registro funcional y el técnico
- **AND** declara que el perfil de agente ajusta la voz, no el alcance

#### Scenario: El user prompt no pide citas inline
- **WHEN** se renderiza `answer/v1/user.j2`
- **THEN** el texto no pide citar con `[document_id · section]` en el cuerpo
- **AND** pide el cierre `Fuentes citadas:`

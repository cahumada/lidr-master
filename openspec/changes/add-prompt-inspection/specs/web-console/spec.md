# web-console Delta Specification

## ADDED Requirements

### Requirement: Un administrador puede ver el contexto completo que se le envió al modelo
La consola muestra la evidencia recuperada, la memoria aplicada y el contexto de
base, cada uno por separado y ya interpretado. El prompt real —con sus bloques
numerados, su persona, sus guardrails y el orden en que quedaron— no lo ve nadie,
y reconstruirlo a mano es adivinar justo lo que produce las respuestas malas.

La pantalla de respuesta SHALL ofrecer, en un turno que trae `prompt_id`, abrir
el contexto completo en un modal. El modal SHALL pedir el texto al abrirse y no
antes: son unos 60 KB por turno y casi nunca se miran.

El modal SHALL mostrar el `system` y el `user` como texto plano preformateado,
separados y rotulados, más con qué se armaron: el modelo, el perfil y el
presupuesto. SHALL NOT renderizarlo como markdown — el prompt se audita por lo
que dice literalmente, y formatearlo esconde justo los caracteres que importan.

#### Scenario: Abrir el contexto
- **WHEN** un administrador abre el modal en un turno con `prompt_id`
- **THEN** ve el `system` y el `user` tal como se enviaron, rotulados por separado
- **AND** ve el modelo, el perfil y el presupuesto con que se armaron

#### Scenario: Se pide al abrir
- **WHEN** el turno se renderiza y el modal está cerrado
- **THEN** el texto del prompt no se pidió

#### Scenario: Literal, no markdown
- **WHEN** el prompt contiene markdown o etiquetas
- **THEN** se ven como texto
- **AND** no se renderizan

#### Scenario: Turno sin prompt
- **WHEN** el turno no trae `prompt_id` —no hubo síntesis, o el snapshot no lo trajo—
- **THEN** no se ofrece el link

#### Scenario: Un prompt que ya venció
- **WHEN** el servicio responde 404 porque la retención lo borró
- **THEN** el modal lo dice
- **AND** no se muestra un modal vacío como si el prompt estuviera en blanco

### Requirement: El rechazo por rol DEBE estar en el servidor, no en si se pinta el link
El prompt lleva la persona y los guardrails —cómo responde el producto— más el
contenido íntegro del corpus recuperado. Sólo el rol `administrador` puede verlo.

`/answer` NO es una pantalla de administración: cualquiera con sesión la abre. El
gate por directorio de `(admin)/` no la alcanza, así que ocultar el link SHALL
ser presentación y no protección. La ruta que sirve el prompt SHALL resolver la
sesión en el servidor y SHALL responder 403 a quien no sea `administrador`,
**antes** de llamar al servicio IA.

#### Scenario: Un usuario no ve el link
- **WHEN** un `usuario` mira un turno con `prompt_id`
- **THEN** no se ofrece abrir el contexto

#### Scenario: Un usuario que pide la ruta igual
- **WHEN** un `usuario` llama a la ruta del prompt directamente
- **THEN** responde 403
- **AND** el servicio IA no se llegó a llamar

#### Scenario: Sin sesión
- **WHEN** la ruta se llama sin sesión resuelta
- **THEN** responde 403

#### Scenario: Un rol que la consola no conoce
- **WHEN** el token trae un rol desconocido
- **THEN** se trata como el rol menos privilegiado
- **AND** responde 403

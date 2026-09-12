# answer-generation Delta Specification

## MODIFIED Requirements

### Requirement: El bloque de contexto DEBE tener un techo en tokens
Antes de renderizar el prompt, los hits pasan por un presupuesto de tokens
(`ANSWER_MAX_CONTEXT_TOKENS`). El conteo se hace sobre el **bloque
renderizado** de cada hit —encabezado `[document_id · section]`, título,
ruta y texto—, no sobre el texto pelado: los delimitadores son tokens que el
modelo va a recibir igual.

El conteo usa el tokenizer de los embeddings (`count_tokens()`), que NO es
el del modelo que responde. Es una estimación con margen, deliberada: el
servicio es multi-proveedor y no existe un conteo exacto disponible
localmente para todos los proveedores del catálogo.

El presupuesto acota el bloque de contexto, no el prompt entero. El system
prompt y la persona quedan afuera del cálculo.

**Adentro de ese techo entran tres bloques, en un orden fijo**: primero la
evidencia recuperada, después la memoria de conversación, y último el bloque de
lo que declara la base fuente. Ninguno de los dos últimos se cobra encima del
techo, y ninguno puede quitarle presupuesto a uno anterior. El orden vive en
`build_budgeted_messages` y no en cada call site, para que no se pueda equivocar
de a un llamador por vez.

El orden no es arbitrario: un chunk desplazado cuesta una cita, un turno de
memoria desplazado rompe el hilo de una conversación, y el bloque de base es el
único de los tres que puede **declarar adentro suyo** lo que perdió — por eso es
el que se recorta primero.

#### Scenario: La evidencia entra completa
- **WHEN** el costo en tokens de todos los hits es menor o igual al
  presupuesto
- **THEN** el prompt lleva todos los hits, en el orden en que llegaron
- **AND** `context_truncated` es false y `dropped_hits` es 0

#### Scenario: La evidencia excede el presupuesto
- **WHEN** el costo acumulado supera `ANSWER_MAX_CONTEXT_TOKENS`
- **THEN** el prompt lleva solo los hits que entran dentro del presupuesto
- **AND** `context_truncated` es true
- **AND** `dropped_hits` es la cantidad de hits que quedaron afuera

#### Scenario: Un chunk nunca se parte al medio
- **WHEN** el siguiente hit no entra completo en el presupuesto restante
- **THEN** ese hit se descarta entero
- **AND** no se emite una porción de su texto

#### Scenario: Un presupuesto inválido se rechaza al arrancar
- **WHEN** `ANSWER_MAX_CONTEXT_TOKENS` se configura en 0 o negativo
- **THEN** la validación de `Settings` falla en el arranque
- **AND** el valor NO se interpreta como «sin límite»

#### Scenario: El orden de ajuste de los tres bloques
- **WHEN** se arma el prompt con evidencia, memoria y bloque de base
- **THEN** la evidencia se ajusta primero contra el presupuesto entero
- **AND** la memoria toma lo que quede después de la evidencia
- **AND** el bloque de base toma lo que quede después de la memoria

#### Scenario: El bloque de base no desplaza nada
- **WHEN** la evidencia y la memoria consumieron todo el presupuesto
- **THEN** el bloque de base no se emite
- **AND** ningún chunk ni turno se descarta para dejarlo entrar
- **AND** la respuesta declara que el bloque quedó afuera por presupuesto

### Requirement: El prompt DEBE instruir anclaje, síntesis, fuentes al final e insuficiencia
El system prompt dice cuatro cosas que el resto del sistema puede observar:
responder solo con el contexto recuperado; redactar una explicación continua
y no reenviar los bloques; no citar `[document_id · section]` en el cuerpo
y cerrar toda la respuesta con `Fuentes citadas:` y los `document_id`
usados; declarar la frase fija de insuficiencia cuando el contexto no
alcanza. Cada chunk entra al user prompt con su procedencia visible —para
que el modelo sepa qué códigos copiar al cierre—, no como texto pelado, y
el user prompt no le pide citar en el cuerpo.

Las cinco reglas siguen primero. Persona, guardrails de operador, el bloque de
memoria (cuando hay) y el bloque de lo que declara la base (cuando hay) se
appendean después y se declaran subordinados: no pueden pedir inventar, omitir el
cierre de fuentes ni salir del contexto.

El bloque de base entra **rotulado como otra autoridad**: no es documentación
funcional, es lo que la base del sistema declara hoy. Ante una diferencia entre
las dos, el prompt pide señalarla y no elegir una — y pide no afirmar que un
catálogo está completo cuando el propio bloque declara que quedó algo afuera.

Las versiones del prompt: `v1` sin memoria y sin base, `v2` con memoria, `v3` con
bloque de base —lleve memoria o no—. `v1` y `v2` quedan congelados y siguen
renderizando byte a byte, porque una respuesta producida con el bloque de base no
es comparable con una producida sin él y el eval tiene que poder distinguir dos
corridas por algo más que una esperanza.

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

#### Scenario: El bloque de base elige la versión del prompt
- **WHEN** se renderiza el prompt con bloque de base
- **THEN** la versión renderizada es `v3`
- **AND** una corrida sin bloque de base sigue renderizando `v1` o `v2`

#### Scenario: `v3` sin bloque de base no cambia el texto
- **WHEN** se renderiza `v3` sin bloque de base y con memoria
- **THEN** el texto es el mismo que produce `v2` con esa memoria

#### Scenario: El bloque de base se declara subordinado y con su autoridad
- **WHEN** se renderiza `answer/v3/system.j2` con bloque de base
- **THEN** el texto declara que ese bloque no es documentación funcional
- **AND** pide reportar la diferencia con la especificación en vez de elegir una
- **AND** pide no afirmar completitud cuando el bloque declara que falta algo
- **AND** las reglas de anclaje siguen apareciendo antes

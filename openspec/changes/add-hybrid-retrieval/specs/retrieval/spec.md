# retrieval Delta Specification

## ADDED Requirements

### Requirement: Una consulta por identificador DEBE encontrar lo que nombra
El corpus se habla por código: un usuario pregunta por `CAC011`, por la tabla
`premium_mo`, por el campo `nReceipt`, por el error `10208`. La búsqueda
vectorial no los encuentra —medido, `CAC011` no aparece entre los cinco primeros
y ninguno de esos cinco contiene el término— y la tokenización del full-text los
destroza: parte por el guion bajo, stemea y descarta lo que parece stopword.

Por eso hay un camino que pregunta por lo que un identificador realmente es:
`document_id`, `field`, o coincidencia literal en el texto.

#### Scenario: Código de transacción
- **WHEN** la consulta es `CAC011`
- **THEN** el documento `CAC011` sale en el primer puesto

#### Scenario: Nombre de tabla o de campo
- **WHEN** la consulta menciona `premium_mo` o `nReceipt`
- **THEN** los resultados contienen chunks donde ese término aparece literalmente

#### Scenario: Código de error entre palabras
- **WHEN** la consulta es `codigo de error 10208`
- **THEN** se devuelven los chunks que contienen `10208`

#### Scenario: Una pregunta en lenguaje natural no dispara el camino exacto
- **WHEN** la consulta no tiene forma de identificador
- **THEN** el camino exacto no se ejecuta

### Requirement: El full-text DEBE combinar los términos con OR, no con AND
`plainto_tsquery` los combina con `AND`, y por eso `codigo de error 10208`
devolvía cero resultados aunque `10208` esté en dos chunks del corpus: no está
junto a las palabras "código" y "error".

Con `OR` cada término aporta y el ranking se encarga de que el chunk que tiene
más términos quede más arriba. Trae más candidatos, incluidos malos; la fusión
los ordena. Un candidato malo que la fusión hunde es mejor que un resultado
correcto que nunca aparece.

#### Scenario: Términos que no coexisten
- **WHEN** ningún chunk contiene todos los términos de la consulta
- **THEN** se devuelven los chunks que contienen algunos
- **AND** los que contienen más quedan más arriba

### Requirement: Los rankings SE DEBEN fusionar por posición, no por puntaje
La distancia coseno vive en [0, 2] y `ts_rank_cd` no tiene tope y depende de la
longitud del texto. No son comparables, y normalizarlos exige mínimos y máximos
que cambian con cada consulta: el puntaje de un resultado terminaría dependiendo
de con quiénes salió.

Reciprocal Rank Fusion combina posiciones (`peso / (k + posición)`). No hay nada
que calibrar.

#### Scenario: Aparecer en dos caminos vale más que ganar en uno
- **WHEN** un chunk sale segundo en el vectorial y segundo en el léxico, y otro
  sale primero solo en el léxico
- **THEN** el primero queda por encima en el resultado fusionado

#### Scenario: Un camino vacío no rompe la fusión
- **WHEN** uno de los caminos no devuelve nada
- **THEN** el resultado es el de los demás, fusionado

#### Scenario: Sin duplicados
- **WHEN** el mismo chunk sale en más de un camino
- **THEN** aparece una sola vez en el resultado

### Requirement: La diversidad por documento DEBE ser un parámetro, no una regla
Medido sobre 8 preguntas reales: el documento dominante se lleva 4,5 de 10 hits
en promedio. En una pregunta general eso es un defecto —7 de 10 de `CA001k`, que
es la solicitud de clave y no la transacción principal—. En una pregunta
específica es la respuesta correcta: los 10 chunks de `AGL009` para una pregunta
sobre la lógica de `AGL009`.

Forzar diversidad arreglaría el primer caso rompiendo el segundo.

#### Scenario: Sin tope
- **WHEN** no se pide tope por documento
- **THEN** el resultado puede traer varios chunks del mismo documento

#### Scenario: Con tope
- **WHEN** se pide un tope de N chunks por documento
- **THEN** ningún documento aporta más de N
- **AND** los lugares liberados los ocupan los siguientes de la fusión

### Requirement: Cada resultado DEBE decir de dónde vino
Un chunk sin procedencia no se puede verificar, y la capa de generación tiene que
poder citar. Cada hit lleva su documento, su sección, su breadcrumb y por qué
camino entró.

#### Scenario: Procedencia
- **WHEN** se devuelve un resultado
- **THEN** lleva `document_id`, `section`, el breadcrumb y los caminos que lo
  encontraron

### Requirement: La calidad de la recuperación DEBE ser un número, con sus límites escritos
Sin métrica, "mejoró" es una opinión. 1.871 documentos tienen título único, lo
que da un conjunto etiquetado: el título como consulta, sus chunks como respuesta
esperada. Línea base con el vector solo: recall@1 70%, recall@5 88%,
recall@10 92%.

Los límites se declaran junto al número, porque un número sin sus límites se
convierte en una afirmación que no se sostiene:

- Un título no es una pregunta real; la métrica premia parecerse al título.
- El techo no es 100%: por eso se usan solo los títulos únicos.
- Un fallo contado puede ser correcto: `VIC014_k` devolvió `SGC001_k`, que tiene
  el título idéntico.

Sirve para comparar dos versiones del mismo sistema, no para afirmar que el
sistema es bueno. La evaluación con preguntas reales necesita conocimiento del
negocio y queda pendiente, no simulada.

#### Scenario: Medición reproducible
- **WHEN** se corre la evaluación sobre el mismo corpus y la misma configuración
- **THEN** da el mismo recall

#### Scenario: El reporte lleva los límites
- **WHEN** la evaluación escribe su reporte
- **THEN** incluye qué mide, sobre cuántos documentos, y qué no se puede
  concluir de él

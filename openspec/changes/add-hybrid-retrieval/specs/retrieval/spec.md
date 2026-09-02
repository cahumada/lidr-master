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

Reciprocal Rank Fusion combina posiciones (`1 / (k + posición)`), con `k = 60`,
el mismo constante que usa el curso (Cormack et al.). No hay nada que calibrar.

**Sin pesos por rama.** El curso deliberadamente no los tiene, y un peso
reintroduce la calibración manual que RRF evita — con el agravante de que un peso
mal elegido es invisible, porque el orden resultante sigue pareciendo razonable.

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

#### Scenario: Todas las ramas pesan igual
- **WHEN** se fusiona
- **THEN** la contribución de un resultado depende solo de su posición y de `k`,
  nunca de un peso por rama

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

### Requirement: Lo que se reporta DEBE ser precision@k sobre un golden set anotado
Es lo que hace el curso (`scripts/eval_retrieval_s10.py`: `hits / k`, por
configuración con nombre, más latencia) y mide lo que importa: de los k que van a
entrar al contexto del generador, cuántos sirven.

El golden set DEBE llevar **distractores deliberados** —documentos parecidos pero
irrelevantes—. Sin ellos se mide si el sistema encuentra, no si sabe descartar, y
los fallos que este cambio ataca son justamente de descarte.

#### Scenario: Reporte por configuración
- **WHEN** se corre la evaluación
- **THEN** informa precision@k y latencia por cada configuración con nombre,
  para poder compararlas

#### Scenario: Medición reproducible
- **WHEN** se corre sobre el mismo corpus y la misma configuración
- **THEN** da el mismo resultado

### Requirement: El golden set NO DEBE darse por válido sin revisión humana
Un golden set escrito por el mismo sistema que después se evalúa contra él no
mide nada: mide si el sistema coincide consigo mismo.

Las preguntas se borradorean de secciones reales del corpus, y el archivo DEBE
declarar que está pendiente de revisión hasta que alguien que conozca el negocio
lo confirme.

#### Scenario: Borrador sin revisar
- **WHEN** el golden set todavía no fue revisado
- **THEN** el archivo lo declara, y el reporte de la evaluación lo repite

#### Scenario: Una pregunta lleva sus documentos relevantes
- **WHEN** se agrega una pregunta al golden set
- **THEN** lleva la lista de documentos que la responden, no uno solo

### Requirement: El proxy de títulos NUNCA DEBE reportarse como calidad del sistema
1.871 documentos tienen título único, lo que da un conjunto etiquetado sin anotar
nada. Corre en segundos y sirve para ver si un ajuste de la fusión mejora o
empeora mientras se itera.

Pero un título no es una pregunta, y la métrica premia parecerse al título: un
cambio que ayude a los títulos y no a las preguntas se vería como una mejora. Su
techo tampoco es 100% —349 documentos comparten título— y un fallo contado puede
ser correcto: `VIC014_k` devolvió `SGC001_k`, que tiene el título idéntico.

Línea base con el vector solo: acierto@1 70%, @5 88%, @10 92%.

#### Scenario: El proxy dice qué es
- **WHEN** el proxy escribe su reporte
- **THEN** declara que es un proxy para comparar versiones, no la calidad del
  sistema, y enumera sus límites

#### Scenario: Sirve para comparar
- **WHEN** se corre el proxy antes y después de un cambio en la fusión
- **THEN** la diferencia dice si ese cambio mejoró o empeoró la recuperación

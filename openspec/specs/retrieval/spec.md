# retrieval Specification

## Purpose

Recuperar los chunks que responden una pregunta sobre las especificaciones
funcionales de Visual Time, y hacerlo de forma verificable: cada resultado dice
de qué documento y de qué sección salió, y por qué camino se encontró.

Tres caminos de recuperación fusionados por posición, una descomposición que
mete al candidato lo que una pregunta compuesta entierra, y un reranker que
ordena lo que quedó adentro. Cada pieza entró con su medición contra un golden
set de 35 preguntas reales de usuarios sobre polizas, siniestros, cobranzas y
diseñador.

Promovido de: `add-hybrid-retrieval`, `add-query-decomposition`, `add-reranker`.

## Requirements

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

### Requirement: La búsqueda DEBE exponerse como `GET` y llevar su procedencia
Una búsqueda no crea nada y es idempotente, así que va en `GET`: la consulta
adentro de la URL se comparte y se cachea, y los filtros son query params por lo
mismo.

Y cada resultado tiene que poder verificarse contra su documento. Estas son
reglas de negocio de seguros; una respuesta que el usuario no puede rastrear
hasta la sección que la respalda no sirve, aunque sea correcta.

#### Scenario: La consulta y los filtros son query params
- **WHEN** se llama `GET /search?q=...&module_code=CA`
- **THEN** se devuelven los chunks relevantes dentro de ese módulo

#### Scenario: Cada hit lleva su procedencia
- **WHEN** se devuelve un resultado
- **THEN** lleva `document_id`, `document_title`, `section`, `bullet_path`,
  `module_code`, el `content_hash` que lo identifica, y `branches` con `ranks`
  diciendo qué camino lo encontró y en qué puesto

#### Scenario: La respuesta dice cómo se produjo
- **WHEN** se devuelve una búsqueda
- **THEN** dice en qué subconsultas se dividió, si un reranker la reordenó, y
  cuántas filas aportó cada camino

#### Scenario: Los defaults son la configuración medida
- **WHEN** no se pasan parámetros de pipeline
- **THEN** se usa tope de 1 chunk por documento, descomposición y reranker
- **AND** el camino léxico queda apagado, porque medido baja el acierto@1 de 77%
  a 48%

#### Scenario: Una consulta que no puede recuperar nada se rechaza
- **WHEN** la consulta tiene menos de 2 caracteres
- **THEN** se responde 422

### Requirement: Los filtros de módulo y tipo de ventana DEBEN aceptar varios valores
`module_code` y `window_type_name` en `GET /search` SHALL aceptar el parámetro
repetido (`?module_code=CA&module_code=DF`) y filtrar con semántica OR entre
los valores dados — un chunk que matchea cualquiera de ellos entra al
candidato. No pasar el parámetro SHALL significar sin filtro, igual que hoy.

#### Scenario: Varios módulos
- **WHEN** se llama `GET /search?q=...&module_code=CA&module_code=DF`
- **THEN** se devuelven chunks cuyo `module_code` es `CA` o `DF`

#### Scenario: Un solo valor se comporta como antes
- **WHEN** se llama `GET /search?q=...&module_code=CA`
- **THEN** el resultado es el mismo que con la igualdad de un solo valor

#### Scenario: Sin el parámetro no hay filtro
- **WHEN** no se pasa `module_code` ni `window_type_name`
- **THEN** la búsqueda no se restringe por esos campos

### Requirement: Los valores disponibles de un filtro SE DEBEN poder listar
`GET /search/facets` SHALL devolver los valores distintos, no nulos y
ordenados de `module_code` y `window_type_name` presentes en el corpus del
`tenant_id`/`doc_version` configurados. Ninguna pantalla ni cliente SHALL
mantener una lista propia de esos valores: siempre sale de este endpoint.

#### Scenario: Valores presentes en el corpus
- **WHEN** se llama `GET /search/facets`
- **THEN** se devuelven los `module_code` y `window_type_name` distintos que
  tienen al menos un chunk cargado
- **AND** ningún valor nulo aparece en ninguna de las dos listas

#### Scenario: Corpus vacío
- **WHEN** no hay chunks cargados para el `tenant_id`/`doc_version` vigente
- **THEN** `GET /search/facets` devuelve ambas listas vacías, no un error

### Requirement: Una pregunta compuesta DEBE preguntarse también por partes
Los usuarios de este sistema no preguntan una cosa por vez. De las 35 preguntas
reales del golden set, 24 son compuestas, y ahí está **toda** la pérdida de
recall: los 15 pares pregunta-documento cuyo documento no aparecía en un
candidato de 60 son de preguntas compuestas, y ninguno de preguntas simples.

El documento no es el problema. Diez de los que faltaban son la respuesta
anotada de otra pregunta, simple, del mismo conjunto: `CA003` sale **primero**
para *"cuántos dígitos tiene la CBU"* y está afuera del top-60 de la pregunta de
domiciliación PAC/TRANSBANK que lo tiene anotado como relevante.

Es la consulta compuesta la que lo entierra, así que se pregunta también por
partes y lo que las partes encuentran se agrega al candidato.

#### Scenario: Cláusulas coordinadas
- **WHEN** la pregunta tiene varias cláusulas, cada una con su interrogativo
- **THEN** se divide en una subconsulta por cláusula
- **AND** el contexto anterior al `¿` aparece en todas, porque ahí están las
  entidades

#### Scenario: Frases nominales coordinadas
- **WHEN** la pregunta comparte un interrogativo y un verbo entre varias frases
  nominales, cada una encabezada por un determinante
- **THEN** se divide en una subconsulta por frase, con la cabeza compartida

#### Scenario: Una pregunta simple no se divide
- **WHEN** la pregunta hace una sola cosa
- **THEN** el divisor devuelve una lista vacía y se busca una sola vez

#### Scenario: Una coma que no separa preguntas no divide
- **WHEN** la coma precede a una subordinada y no a un interrogativo ni a un
  determinante
- **THEN** la pregunta no se divide

### Requirement: La descomposición NO DEBE cambiar el orden de lo que ya se encontraba
Se midieron tres formas de combinar las subconsultas con la consulta completa
[VERIFICADO-CORPUS]:

| variante | rescata al top-10 | **rompe** |
|---|---:|---:|
| fusionar solo las subconsultas | 7 | **7** |
| fusionar completa + subconsultas | 5 | **4** |
| agregar sin reordenar | 0 | **0** |

Fusionar solo las partes da empate exacto porque RRF **diluye**: un documento en
el puesto 3 de la consulta completa y ausente de las tres partes puntúa menos
que uno en el puesto 20 de la completa y en el 5 de dos partes.

Por eso el candidato empieza con exactamente lo que devolvió la consulta
completa, en su orden, y las subconsultas solo aportan lo que no estaba.

#### Scenario: El prefijo se conserva
- **WHEN** se descompone una consulta
- **THEN** el resultado empieza con los mismos chunks y en el mismo orden que
  sin descomponer

#### Scenario: Lo agregado llena lugares vacíos
- **WHEN** la consulta completa devuelve menos resultados que el límite pedido
- **THEN** las subconsultas llenan los puestos libres sin desplazar nada

### Requirement: La descomposición DEBE medirse por recall del candidato y no por precision@k
`precision@10` no se mueve con este cambio —0,140 antes y después— y reportarlo
solo con esa métrica lo haría parecer inútil.

No lo es, y la razón es una división de trabajo: la descomposición hace que el
documento **entre** al candidato; ordenarlo es de un reranker. Medida en lo que
le corresponde, sobre las 35 preguntas humanas [VERIFICADO-CORPUS]:

| | base | con descomposición |
|---|---:|---:|
| `recall@60` | 70/85 (82%) | **77/85 (91%)** |
| pares alcanzables por un reranker | 21 | **28** |
| pares perdidos | 15 | **8** |
| regresiones | — | **0** |

#### Scenario: El reporte separa rango de recall
- **WHEN** se evalúa una configuración
- **THEN** se reporta cuántos pares están en el top-k, cuántos entre el puesto
  k+1 y el ancho del candidato, y cuántos afuera
- **AND** los del medio son los que un reranker puede convertir; los de afuera
  no, porque reordenar no trae lo que no vino

### Requirement: El candidato DEBE poder reordenarse antes de recortarse a k
Después de la descomposición, 27 de los 85 pares pregunta-documento del golden
set tienen su documento en el candidato de 60 y afuera del top-10. Un oráculo
—un reranker perfecto— convierte 28 y lleva `p@10` de 0,140 a 0,220, que es el
91% del techo teórico de este conjunto.

Reordenar los mismos k que la búsqueda ya eligió no tiene con qué trabajar, así
que el reranker ve el candidato ancho y el recorte a `limit` pasa después.

#### Scenario: El candidato se ensancha antes de reordenar
- **WHEN** se pide `limit=10` con un reranker
- **THEN** la fusión produce `rerank_candidates` resultados, se reordenan, y se
  devuelven los primeros 10

#### Scenario: Se reordena lo hidratado
- **WHEN** el reranker recibe los candidatos
- **THEN** cada uno lleva título, sección y texto, porque es por eso que juzga

#### Scenario: Sin reranker nada cambia
- **WHEN** no se pasa reranker
- **THEN** el resultado es exactamente el de la fusión, recortado a `limit`

### Requirement: El reranker NO DEBE descartar candidatos
Reordena, no filtra. El modelo devuelve menos de 10 ids en 25 de 35 consultas, y
si el reranker se quedara solo con lo elegido, esas consultas devolverían 6
resultados en lugar de 10.

#### Scenario: Lo no elegido va detrás
- **WHEN** el reranker elige 3 de 60 candidatos
- **THEN** devuelve los 60: los 3 primero y los 57 restantes en su orden previo

### Requirement: Un id que no está entre los candidatos DEBE descartarse
Un id inventado por el modelo devolvería al usuario un documento que la búsqueda
nunca encontró, con procedencia falsa. Medido: 1 en 35 consultas con
`gpt-4o-mini`, 0 con `gpt-4o`. Poco, pero no cero.

#### Scenario: Alucinación
- **WHEN** el modelo devuelve un id que no estaba en la lista
- **THEN** se descarta, se cuenta y se loguea

#### Scenario: Id repetido
- **WHEN** el modelo devuelve el mismo id dos veces
- **THEN** aparece una sola vez en el resultado

### Requirement: Un reranker que falla NO DEBE llevarse la consulta puesta
El orden fusionado es una respuesta real, medida en `p@10` 0,140. Propagar un
503 del proveedor lo convertiría en un error.

#### Scenario: El modelo levanta
- **WHEN** la llamada falla o devuelve un JSON inválido
- **THEN** se devuelven los candidatos como llegaron, y se loguea el fallo

#### Scenario: Sin clave de API
- **WHEN** no hay `OPENAI_API_KEY`
- **THEN** se usa el reranker léxico, que vale +4 pares medidos, en lugar de
  fallar

### Requirement: La ganancia de un reranker DEBE reportarse con sus regresiones
Un reranker **no puede** ser libre de regresiones: hay k puestos y promover un
documento baja a otro. Es de suma cero, y es la diferencia con la
descomposición, que sí lo es por construcción.

Medido, el de modelo rescata 15-16 pares y rompe 6-7. Reportar solo el neto
escondería la mitad de lo que hace.

Y `temperature=0` no es determinismo: tres corridas idénticas dieron 57, 58 y 59
pares en el top-10. La ganancia se reporta como rango, no como la mejor corrida.

#### Scenario: El reporte separa rescates de roturas
- **WHEN** se evalúa una configuración con reranker
- **THEN** se reporta cuántos pares entraron al top-k y cuántos salieron

### Requirement: Cada hit DEBE declarar si es contenido o navegación
`document_kind` distingue un chunk que responde algo (`content`) de un nodo de
navegación (`index`) — un breadcrumb de una línea, no una respuesta. Es
procedencia real, del mismo tipo que ya expone `/search` para que una
respuesta se pueda verificar contra su documento.

#### Scenario: Se expone en la respuesta
- **WHEN** se devuelve un hit de `GET /search`
- **THEN** lleva su `document_kind`

### Requirement: `document_kind` NO DEBE influir en el orden por default
Medido contra 85 pares de un golden set humano: demover candidatos `'index'`
en el ranking dio pérdida neta con cualquier magnitud probada, porque dos
respuestas reales anotadas (`SI001_A`, `DP003_A`) son ellas mismas documentos
`index` — la única evidencia que las sostiene en el top-10 es justo el pilar
que una democión debilita.

#### Scenario: El orden no cambia
- **WHEN** se ejecuta una búsqueda con la configuración por default
- **THEN** el orden es el mismo que si `document_kind` no existiera como
  columna

<!-- Promovido de: add-index-demotion-and-dedup -->

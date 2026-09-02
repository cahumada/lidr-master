# process-map Delta Specification

## ADDED Requirements

### Requirement: Cada arista DEBE declarar su tipo y su fuente
Tres relaciones distintas conviven en el corpus y no afirman lo mismo:
`menu_parent` dice dónde vive una transacción en el menú, `requires` dice que
hay que ejecutar una antes de otra, y `references` dice que un documento
menciona a otro.

Colapsarlas destruye lo que las hace útiles. Los mayores emisores de
`references` son documentos índice —`LIFE_INDEX` con 130— así que un consumidor
que las viera como precedencia concluiría que ese índice tiene 130 dependencias
de proceso.

#### Scenario: Tipo y origen en la arista
- **WHEN** se produce una arista
- **THEN** lleva su `edge_type` y de qué fuente se extrajo

#### Scenario: Una referencia desde un índice se distingue
- **WHEN** la arista sale de un documento cuyo `document_kind` es `index`
- **THEN** queda marcada como tal, para que no se lea como relación de negocio

#### Scenario: Los tipos no se mezclan
- **WHEN** se pide el grafo de precedencia
- **THEN** solo trae aristas `requires`

### Requirement: Una arista de precedencia SOLO DEBE existir si el documento la declara
El mapa va a usarse para responder *"qué tengo que correr antes"*. Una arista
inventada ahí es peor que una faltante.

La dependencia está partida en dos en el fuente: el enunciado dice la semántica
(*"requiere que previamente se ejecute"*) y lo que sigue da los códigos, como
tabla, como lista o como texto plano. Se reconoce el enunciado primero y solo
entonces se toman los códigos.

Se lee la **sección** completa y no cada chunk: la sección `Requisitos` de
`COL502` produce 4 chunks —3 de tabla con los códigos, 1 narrativo con el
enunciado— así que chunk por chunk el enunciado y sus códigos nunca se ven
juntos. Por chunk se extraen 9 aristas; por sección, 39.

Alcance real medido: de 228 secciones `Requisitos`, 122 dicen `No aplica.`, 105
son requisitos de otra clase y **25 declaran precedencia**.

Buscar códigos con una expresión regular sobre toda la sección traería los
mencionados de paso y perdería la dirección: `A requiere B` y `B requiere A` se
escriben con los mismos dos códigos.

#### Scenario: Precedencia declarada con su tabla
- **WHEN** un documento dice que requiere la ejecución previa de otro proceso y
  lo lista a continuación
- **THEN** se produce una arista `requires` del documento al proceso listado

#### Scenario: Requisitos que no son precedencia
- **WHEN** la sección `Requisitos` habla de permisos o de datos cargados, sin
  declarar ejecución previa
- **THEN** no se produce ninguna arista `requires`

#### Scenario: El enunciado y sus códigos en chunks distintos
- **WHEN** el enunciado de precedencia está en un chunk y los códigos en chunks
  de tabla hermanos de la misma sección
- **THEN** las aristas se producen igual

#### Scenario: Códigos como texto plano
- **WHEN** los códigos no están enlazados, solo escritos
- **THEN** se reconocen igual

#### Scenario: Precedencia sin destino nombrable
- **WHEN** un documento declara precedencia sin nombrar un código
- **THEN** queda registrada como dependencia no resuelta, no descartada

#### Scenario: La dirección se conserva
- **WHEN** `CO501` requiere `COL500`
- **THEN** la arista va de `CO501` a `COL500` y no al revés

#### Scenario: No se infiere nada
- **WHEN** dos procesos escriben en la misma tabla pero ninguno declara al otro
- **THEN** no hay arista entre ellos

### Requirement: El mapa DEBE declarar lo que no cubre
Medido sobre el corpus [VERIFICADO-CORPUS]: **794 de 3.389** transacciones (23%)
no son alcanzables desde ningún menú, 1.850 nodos del árbol no tienen documento
funcional, y 672 documentos no son una ventana.

"No alcanzable" es que su camino **no llega a la raíz**, no simplemente que no
tenga padre. Son dos números distintos y el correcto es el primero: 717 códigos
no tienen padre, pero 3 de ellos **sí tienen hijos**, y cada descendiente de un
subárbol colgado de la nada es tan inalcanzable como su raíz. Contar solo los
sin padre daba 714 y subcontaba por 80.

Ninguno es un error a corregir: es cómo es el sistema. Pero un mapa que los
omitiera se leería como completo y llevaría a afirmar que una transacción no
existe cuando lo que pasa es que no está en el menú.

#### Scenario: Cobertura en el artefacto
- **WHEN** se construye el mapa
- **THEN** el artefacto lleva cuántas transacciones no cuelgan de un menú,
  cuántos nodos no tienen documento y cuántos documentos no son ventana

#### Scenario: Una transacción sin menú sigue en el mapa
- **WHEN** una transacción existe como ventana y su camino no llega a la raíz
- **THEN** está en el mapa, marcada como no alcanzable desde el menú

#### Scenario: Un subárbol entero colgado de la nada
- **WHEN** un código sin padre tiene hijos
- **THEN** él y todos sus descendientes quedan marcados como no alcanzables

#### Scenario: La raíz no se cuenta como inalcanzable
- **WHEN** se evalúa la raíz del árbol, que no tiene padre por definición
- **THEN** no queda marcada como no alcanzable

#### Scenario: El grafo no tiene ciclos que cuelguen a quien lo recorra
- **WHEN** el árbol fuente contiene un ciclo
- **THEN** se detecta y se reporta, y el recorrido termina

### Requirement: El contexto del CAG DEBE medirse y NUNCA truncarse en silencio
Un CAG solo sirve si lo precargado entra en la ventana. El tamaño se mide con el
mismo tokenizador que usa el chunker, no se estima por caracteres.

Si supera el techo configurado, la construcción **falla**. Truncar un mapa por la
mitad es peor que no tenerlo: lo que queda parece completo.

#### Scenario: Tamaño medido
- **WHEN** se genera el contexto
- **THEN** su cuenta de tokens se calcula con el tokenizador del modelo

#### Scenario: Por encima del techo
- **WHEN** el contexto supera el techo configurado
- **THEN** la construcción falla diciendo cuánto se pasó
- **AND** no escribe un contexto truncado

#### Scenario: El contexto declara sus propios límites
- **WHEN** se genera el contexto
- **THEN** incluye qué relaciones cubre y cuáles no, para que quien lo lea sepa
  qué no puede afirmar

### Requirement: El mapa DEBE quedar en las dos formas que sus consumidores necesitan
El contexto del CAG se precarga entero y es texto. La recuperación necesita
preguntar *"¿qué referencia a `CA014`?"* para una consulta puntual, y cargar el
grafo completo para eso sería absurdo.

#### Scenario: Artefacto reproducible
- **WHEN** se construye el mapa
- **THEN** queda un JSON con nodos y aristas, del que se puede regenerar todo

#### Scenario: Consulta puntual por una punta
- **WHEN** se pregunta qué aristas entran o salen de una transacción
- **THEN** se responde desde la tabla, sin leer el artefacto completo

#### Scenario: Carga idempotente
- **WHEN** se carga el mapa dos veces
- **THEN** la segunda no duplica ninguna arista

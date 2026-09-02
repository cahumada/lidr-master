# retrieval Delta Specification

## ADDED Requirements

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

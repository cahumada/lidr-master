# retrieval Delta Specification

## ADDED Requirements

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

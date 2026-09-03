# retrieval Delta Specification

## ADDED Requirements

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

# vector-store Delta Specification

## ADDED Requirements

### Requirement: El modo TLS DEBE traducirse entre los dos drivers
Los dos stacks salen de un solo `DATABASE_URL`. libpq escribe el modo TLS como
`sslmode` y el `connect()` de asyncpg lo escribe como `ssl`, con el **mismo
vocabulario** de valores.

Sin la traducción, una URL con `?sslmode=require` falla al conectar solo en el
camino async: las migraciones y el `COPY` andan, así que todo parece haber
funcionado y la búsqueda es lo único roto.

#### Scenario: Del lado async
- **WHEN** la URL configurada lleva `sslmode`
- **THEN** el camino asincrónico recibe el mismo valor bajo `ssl`

#### Scenario: Del lado sync
- **WHEN** la URL configurada lleva `ssl`
- **THEN** el camino sincrónico recibe el mismo valor bajo `sslmode`

#### Scenario: El significado no cambia
- **WHEN** el modo es cualquiera de los de libpq
- **THEN** el valor pasa sin modificarse, porque asyncpg parsea ese mismo
  vocabulario

#### Scenario: Una URL sin modo TLS no se toca
- **WHEN** la URL no declara modo TLS
- **THEN** solo se cambia el token del driver

#### Scenario: La contraseña sobrevive a la reescritura
- **WHEN** se reescribe una URL con contraseña
- **THEN** la contraseña sigue ahí, porque una URL enmascarada no conecta con
  nada

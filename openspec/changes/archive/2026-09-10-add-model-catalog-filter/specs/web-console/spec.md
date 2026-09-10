# web-console Delta Specification

## ADDED Requirements

### Requirement: El catálogo de modelos se filtra en el cliente
La pantalla de Modelos SHALL ofrecer, por proveedor, un filtro por substring
del nombre del modelo y un recorte por visibilidad (todos / ofrecidos /
ocultos). El filtro SHALL recortar la lista ya cargada: NO SHALL emitir una
llamada nueva al servicio. Con cero coincidencias, SHALL decirlo en vez de
dejar la lista vacía sin explicación.

#### Scenario: filtrar el catálogo de OpenAI
- **WHEN** el usuario escribe `gpt-5` en el filtro de OpenAI
- **THEN** la lista de ese proveedor solo muestra modelos cuyo nombre contiene
  `gpt-5`
- **AND** no se emite ninguna request de red

#### Scenario: ningún modelo coincide
- **WHEN** el filtro no coincide con ningún modelo del proveedor
- **THEN** la pantalla informa que no hay coincidencias
- **AND** no muestra filas de otros proveedores en esa lista

### Requirement: Cada proveedor conocido enlaza a su tabla de precios
Para los proveedores de la semilla (`openai`, `anthropic`, `moonshot`) la
ficha SHALL exponer un enlace externo a la página oficial donde el proveedor
publica el precio por millón de tokens. El enlace SHALL abrirse en otra
pestaña. Un proveedor que no está en esa lista SHALL no mostrar ningún
enlace de precios.

#### Scenario: ficha de OpenAI
- **WHEN** el usuario abre Configuración → Modelos
- **THEN** la ficha de OpenAI muestra un enlace a su página oficial de precios
- **AND** el enlace abre en otra pestaña

#### Scenario: proveedor sin URL conocida
- **WHEN** la ficha es de un proveedor que no está en la semilla
- **THEN** no aparece un enlace de precios

### Requirement: Cada ficha de proveedor se puede colapsar
La pantalla de Modelos SHALL permitir abrir y cerrar cada proveedor por
separado. Colapsada, la ficha SHALL seguir mostrando identidad, estado,
conteo de modelos ofrecidos, el enlace de precios si lo hay, y el switch
de habilitado. El cuerpo (credencial, catálogo, filtros) SHALL quedar
oculto. El estado de cada ficha SHALL ser independiente de las demás.

#### Scenario: colapsar OpenAI
- **WHEN** el usuario colapsa la ficha de OpenAI
- **THEN** no se ven la credencial ni la lista de modelos de OpenAI
- **AND** el nombre, el conteo de ofrecidos y el switch de habilitado siguen
  visibles

#### Scenario: las fichas no se acoplan
- **WHEN** el usuario abre Anthropic y deja OpenAI colapsada
- **THEN** solo Anthropic muestra su cuerpo
- **AND** OpenAI permanece colapsada

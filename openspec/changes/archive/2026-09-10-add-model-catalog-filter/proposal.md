## Why

`POST /config/providers/{id}/models/refresh` deja en la base todo lo que el
proveedor reporta — OpenAI, medido, **124 modelos**. La pantalla de Modelos
los muestra en una lista sin búsqueda: encontrar `gpt-5.6-sol` entre
`babbage-002` y `chatgpt-image-latest` es un scroll. El operador que decide
cuál ofrecer necesita, además, el precio por millón de tokens, y hoy no hay
ningún camino desde la ficha hasta la tabla oficial del proveedor.

## What Changes

- Filtro local por nombre (y por ofrecido/oculto) en el catálogo de cada
  proveedor. No llama al servicio: recorta lo que `GET /config` ya trajo.
- Link externo a la página oficial de precios por millón de tokens, para los
  tres proveedores de la semilla. Un proveedor agregado a mano no inventa
  una URL.
- Cada ficha de proveedor se colapsa: cabecera (nombre, estado, precios,
  habilitado) queda a la vista; credencial y catálogo se esconden.

## Capabilities

### New Capabilities
(ninguna)

### Modified Capabilities
- `web-console`: el catálogo de modelos se puede filtrar, y cada proveedor
  conocido enlaza a su tabla de precios.

## Impact

- `business-backend/lib/provider-docs.ts` (nuevo)
- `business-backend/app/agents/providers-panel.tsx`
- `openspec/changes/add-model-catalog-filter/specs/web-console/spec.md`

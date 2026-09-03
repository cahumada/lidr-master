## Why
En la pantalla de búsqueda de la consola web, `Módulo` y `Tipo de ventana` son
inputs de texto libre de un solo valor: para comparar "CA o DF" hay que correr
dos búsquedas y pegar los resultados a mano, y nada le dice al usuario qué
módulos o tipos de ventana existen realmente en el corpus cargado — hay que
adivinar la ortografía exacta (`"Masivo con encabezado"` vs. `"masivo con
encabezado"`).

El dueño del producto pidió que los dos filtros sean listados de selección
múltiple, con default explícito ("todos" para módulos, "cualquiera" para tipos
de ventana). Eso exige dos cosas que hoy no existen: que `GET /search` acepte
varios valores por filtro (semántica OR, no una sola igualdad), y una forma de
listar los valores que realmente aparecen en el corpus para poblar cada
listado — ninguno de los dos es una lista fija (`module_code` va desde `CA` de
dos letras hasta `DMECAR` de seis, y no hay un enum en la base).

## What Changes
- `ai-service`: `SearchFilters.module_code` y `.window_type_name` pasan de
  `str | None` a `list[str] | None`; `_apply` filtra con `IN` en vez de `=`.
- `ai-service`: `GET /search` acepta `module_code` y `window_type_name`
  repetidos (`?module_code=CA&module_code=DF`) en vez de uno solo.
- `ai-service`: nuevo `GET /search/facets` que devuelve los valores
  distintos de `module_code` y `window_type_name` presentes hoy en el corpus
  (`tenant_id`/`doc_version` vigentes), para poblar los listados.
- `business-backend`: `lib/ai-service/search.ts` gana `facets()`; los tipos y
  `SearchParams` reflejan filtros como arreglos; `/api/search` reenvía
  parámetros repetidos y una ruta nueva `/api/search/facets` expone el
  endpoint de arriba.
- `business-backend`: la pantalla de búsqueda reemplaza los dos inputs de
  texto por listados de checkboxes con una opción "Todos" / "Cualquiera"
  seleccionada por default; los valores de cada listado salen de
  `GET /api/search/facets`, no de una lista escrita a mano.

## Capabilities
### Modified Capabilities
- `retrieval`: los filtros de módulo y tipo de ventana aceptan varios valores
  con semántica OR, y hay un endpoint para listar los valores disponibles.
- `web-console`: la pantalla de búsqueda usa selección múltiple para esos dos
  filtros, con default explícito. `web-console` todavía no está en
  `openspec/specs/` — `add-web-console` sigue en curso — así que este delta se
  integró directo al delta de ese cambio
  (`openspec/changes/add-web-console/specs/web-console/spec.md`) en vez de
  vivir acá; se promueve a `specs/` cuando ese cambio se archive.

## Impact
- `ai-service/app/generation/rag/store/repository.py` — `SearchFilters`, `_apply`, nuevo método de valores distintos.
- `ai-service/app/api/search.py` — query params repetidos, nuevo `GET /search/facets`.
- `ai-service/app/generation/rag/schemas.py` — nuevo `SearchFacets`.
- `ai-service/tests/api/test_search_router.py`, `ai-service/tests/store/test_store_integration.py`, `ai-service/tests/generation/rag/test_retrieval.py` — cubrir `IN` y el endpoint nuevo.
- `business-backend/lib/ai-service/types.ts`, `search.ts` — filtros como arreglos, `facets()`.
- `business-backend/app/api/search/route.ts`, nuevo `business-backend/app/api/search/facets/route.ts`.
- `business-backend/app/search/search-console.tsx`, `business-backend/app/search/page.tsx` — listados de selección múltiple.

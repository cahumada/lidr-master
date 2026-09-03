# Implementation Tasks

## 1. `ai-service`: filtros de varios valores
- [x] 1.1 `SearchFilters.module_code` y `.window_type_name`: `str | None` →
      `list[str] | None`.
- [x] 1.2 `_apply` en `repository.py`: `column.in_(value)` en vez de
      `column == value` para esos dos campos (una lista de un elemento se
      comporta igual que la igualdad de hoy).
- [x] 1.3 `GET /search`: `module_code` y `window_type_name` pasan a
      `list[str] | None = Query(default=None)` para aceptar el parámetro
      repetido.
- [x] 1.4 Actualizar `tests/generation/rag/test_retrieval.py` y cualquier otro
      test que construya `SearchFilters(module_code="X")` a la forma lista.

## 2. `ai-service`: endpoint de valores disponibles
- [x] 2.1 `ChunkRepository`: método que devuelve los `module_code` distintos
      (no nulos) del tenant/doc_version vigente, ordenados; ídem para
      `window_type_name`.
- [x] 2.2 `schemas.py`: `SearchFacets` con `modules: list[str]` y
      `window_types: list[str]`.
- [x] 2.3 `GET /search/facets` en `search.py`, usando el tenant/doc_version de
      `Settings`, igual que `/search`.
- [x] 2.4 Test de router para `/search/facets` (valores distintos, sin nulos,
      ordenados) -- cubierto a nivel integración en
      `tests/store/test_store_integration.py::test_distinct_values_list_what_is_actually_loaded`,
      ya que el router de facets no tiene lógica propia que mockear.

## 3. `business-backend`: capa `lib/ai-service/`
- [x] 3.1 `types.ts`: `SearchParams.module_code`/`.window_type_name` a
      `string[]`; nuevo `SearchFacets`.
- [x] 3.2 `base-client.ts`: `getJson` acepta valores `string[]` en `params` y
      los manda como parámetro repetido.
- [x] 3.3 `search.ts`: nuevo `facets()` que llama a `GET /search/facets`.

## 4. `business-backend`: Route Handlers
- [x] 4.1 `app/api/search/route.ts`: leer `module_code`/`window_type_name`
      con `searchParams.getAll(...)` en vez de `.get(...)`.
- [x] 4.2 Nuevo `app/api/search/facets/route.ts` → reenvía a `facets()`.

## 5. `business-backend`: pantalla de búsqueda
- [x] 5.1 `search-console.tsx`: listado de checkboxes para módulo, con "Todos"
      seleccionado por default; deseleccionar "Todos" al elegir un módulo
      puntual, y volver a "Todos" si no queda ninguno elegido.
- [x] 5.2 Mismo patrón para tipo de ventana, con "Cualquiera" como default.
- [x] 5.3 Los valores de cada listado salen de `facets()`, pedido en el server
      component `page.tsx` y pasado como prop -- nunca de una lista escrita a
      mano en la pantalla.
- [x] 5.4 Estado vacío del listado (el servicio no tiene chunks todavía / el
      facet vino vacío) no rompe la pantalla: `page.tsx` degrada a listas
      vacías si `facets()` falla, y `MultiSelectFilter` muestra un mensaje en
      vez de una lista en blanco.

## 6. Documentación y specs
- [x] 6.1 Delta de `specs/retrieval/spec.md`: filtros de varios valores +
      `/search/facets`.
- [x] 6.2 Delta de `specs/web-console/spec.md`: selección múltiple con
      default.

## 7. Verificación
- [x] 7.1 Desde `ai-service/`: `uv run pytest` (511 passed) y
      `uv run ruff check .` (limpio).
- [x] 7.2 Desde `business-backend/`: `pnpm lint` y `pnpm build` (limpios).
- [x] 7.3 `python scripts/validate_specs.py` en verde.
- [x] 7.4 Smoke local contra el `uvicorn --reload` y el `pnpm dev` ya
      corriendo, con la base real de Railway: `/search/facets` devuelve 17
      módulos y 11 tipos de ventana reales; seleccionar `DMECAR` apaga
      "Todos", manda `module_code=DMECAR` y los 5 resultados devueltos son
      todos de ese módulo; deseleccionarlo vuelve a "Todos" sola.
- [x] 7.5 Promover los deltas a `openspec/specs/` y archivar el cambio.

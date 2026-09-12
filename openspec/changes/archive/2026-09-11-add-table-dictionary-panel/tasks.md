# Implementation Tasks

Misma rama que los changes anteriores: PR único, decisión del dueño.

## 1. La descripción en el prompt

- [x] 1.1 `read_dependency_tables`: `LEFT JOIN` con `business_tables` por
      `(tenant, env, run_id, name)` y poblar `DependencyTable.description`.
      Una consulta, no N+1.
- [x] 1.2 `BUSINESS_DB_CONTEXT_MAX_TOKENS` default 2048 → 3072 en `app/config.py`
      y `.env.example`, con el motivo medido escrito al lado.
- [x] 1.3 Test de que una tabla con ficha emite su descripción y una sin ficha se
      emite igual.

## 2. El diccionario completo

- [x] 2.1 `read_table_dictionary_full()` en `reader.py`: columnas (nombre,
      descripción, tipo, nullable), PK, FK con `refTable`, índices. `columns`
      `NULL` se distingue de `[]`.
- [x] 2.2 `GET /business-db/tables/{name}` en `app/api/business_db.py`: router
      delgado, 404 sin tabla, 409 sin corrida vigente. Schemas Pydantic.
- [x] 2.3 Tests de contrato en `tests/api/test_business_db.py`.
- [x] 2.4 `pytest` (1.087) y `ruff check .` en verde.

## 3. Consola

- [x] 3.1 `TableDictionaryView` y sus tipos en `lib/ai-service/types.ts`;
      `getTableDictionary()` en `lib/ai-service/business-db.ts`.
- [x] 3.2 `app/api/business-db/tables/[name]/route.ts` — relay, sin gate de rol.
- [x] 3.3 `app/(console)/answer/table-dictionary.tsx`: ficha desplegable, pide al
      abrir, filtro por nombre de columna, scroll propio.
- [x] 3.4 `business-db-panel.tsx`: el nombre de la tabla abre la ficha.
- [x] 3.5 `pnpm test` (32), `eslint` y `pnpm build` en verde.

## 4. Specs

- [x] 4.1 Los deltas reflejan lo implementado.
- [x] 4.2 `python scripts/validate_specs.py` sin errores.
- [x] 4.3 `openspec/standards/app-routes.md`: las dos rutas nuevas.

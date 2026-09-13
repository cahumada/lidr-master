# Implementation Tasks

Todo va en `add-dependency-table-anchoring-ai-service`, consola incluida: el
dueño pidió PR único (2026-09-11). El grupo 7 toca `business-backend/`.

## 1. Persistencia de las aristas

- [x] 1.1 `TransactionTableEdge` en `ai-service/app/generation/rag/store/models.py`:
      identidad `(tenant, env, run_id, transaction_code, table_name)`, más
      `role`, `role_reason`, `via_routines` (lista), `fan_in`, `origin`,
      `created_at`. Índice por `(tenant, env, run_id, transaction_code)` — la
      lectura es siempre por código. Va por `run_id` del mirror, **no** por
      `doc_version`.
- [x] 1.2 Migración Alembic para esa tabla. No reformatear `alembic/versions/`.
- [x] 1.3 Tabla de estado por corrida (o columna derivable) que responda «¿esta
      corrida tiene aristas?» sin contar filas en cada request.
- [x] 1.4 **No corresponde.** El `reset` de corpus borra por
      `(tenant_id, doc_version)` y estas tablas van por `(tenant, env, run_id)`
      del mirror: son de otro eje. Borrarlas en una rebuild dejaría al servicio
      sin aristas para una corrida que sigue activa. `transaction_table_builds`
      guarda el `doc_version` que aportó los códigos, que es lo que dice cuándo
      hay que reconstruir.

## 2. Armado de las aristas (sin I/O de red, testeable)

- [x] 2.1 `app/generation/rag/business_db/roles.py`: las reglas ordenadas
      `(patrón, rol)` de `design.md` §3.1 como datos, y `classify_role()` puro que
      devuelve `(role, reason)` — `unknown` con razón cuando ninguna aplica.
      Sin I/O.
- [x] 2.2 `app/generation/rag/business_db/dependencies.py`: el salto por nombre con
      guarda de largo ≥ 5 y desambiguación por munch máximo, y el salto por
      dependencia. Funciones puras sobre listas de códigos, nombres y aristas —
      la lectura del mirror queda afuera.
- [x] 2.3 **Sin umbral de fan-in.** La medición mostró que la regla corre al
      revés (design §3.1), así que el fan-in no degrada nada y no hay umbral que
      configurar. Se guarda en cada arista para poder revisarlo.
- [x] 2.4 Tests en `tests/generation/rag/business_db/test_dependencies.py`:
      `CA013` / `CA013A` (munch máximo), `AG001` / `AG001_K` / `MAG001`, código de
      largo 4, código sin rutinas, rutina sin tablas.
- [x] 2.5 Tests en `tests/generation/rag/business_db/test_roles.py`: un caso por
      regla de §3.1, el orden destino-antes-que-camino, y `unknown` con razón.

## 3. El batch

- [x] 3.1 `ai-service/scripts/build_transaction_tables.py` con `--dry-run`, con el
      mismo patrón que `build_process_map.py`: lee `chunks` (los `document_id`),
      `business_dependencies` y `business_tables` de una corrida, arma las aristas
      con rol, y las persiste con `ON CONFLICT DO NOTHING`.
- [x] 3.2 Reporte de la corrida: documentos anclados, pares código–rutina, aristas
      por rol, ambigüedades resueltas por munch máximo, tablas sin ficha en el
      diccionario. Se escribe al lado del artefacto, como hace el mapa de procesos.
- [x] 3.3 Corrido contra `20260909_214921`: **460 documentos llegan a 1+ tabla,
      957 pares código–rutina, 4.873 aristas**, mediana 7 tablas por documento.
      Menos que los 554 / 1.556 medidos al planear, y a propósito: la guarda de
      borde (design §2.1) descarta los matches que el prefijo verbal fabrica.

## 4. Lectura y bloque

- [x] 4.1 `DependencyTable`, el `Literal` de roles y las causas nuevas
      (`edges_not_built`, `no_dependency_routine`, `routine_without_tables`,
      `code_too_short_to_anchor`, `dependency_tables_capped`, `role_unknown`) en
      `app/generation/rag/business_db/models.py`. Repartirlas entre
      `DECLARED_ABSENT` e `INCOMPLETE_OUTCOMES` según §6 del proposal:
      `edges_not_built` y `dependency_tables_capped` son incompletitud; el resto,
      ausencia declarada.
- [x] 4.2 `reader.py`: lectura de `transaction_table_edges` por código y corrida,
      y el chequeo de «esta corrida tiene aristas» que emite `edges_not_built`.
- [x] 4.3 `render.py`: la sección nueva ordenada **por cobertura** (no por rol),
      con las rutinas de cada tabla; y el orden de recorte de §5 — tablas desde
      la cola, piso de una por código, rutinas nunca recortadas.
- [x] 4.4 **Sin tocar la plantilla.** `v3/user.j2` interpola `business_db`, que
      `render.py` compone entero: la sección entra por el renderer. Sin `v4`.
- [x] 4.5 `BUSINESS_DB_DEPENDENCY_TABLES_ENABLED` (default `false`) y
      `BUSINESS_DB_DEPENDENCY_MAX_TABLES` (default 12) en `app/config.py` y
      `.env.example`.
- [x] 4.6 Tests de render: orden por rol, recorte en el orden declarado, una tabla
      nunca pierde sus rutinas, `dependency_tables_capped` con el conteo real.
- [x] 4.7 Test de que `v1` y `v2` siguen renderizando byte a byte.

## 5. Medición (bloquea la habilitación)

- [x] 5.1 `ai-service/evals/golden_transaction_tables.json` con ~20 transacciones
      anotadas por el dueño del repo. Semilla verificada al planear: `CA014` →
      `COVER`; `CA025` → `ROLES`, `CLIENT`; `CA001` y `CA048` → `POLICY`,
      `CERTIFICAT`, `POLICY_HIS`.
- [x] 5.2 `ai-service/scripts/eval_transaction_tables.py`: **recall@N** de las
      tablas anotadas (no precisión de `core`, que no existe), su posición bajo
      el orden por cobertura, y la distribución de roles. El umbral que habilita
      el flag vive en el script.
- [x] 5.3 Correrlo y dejar las cifras en `evals/` con su `.md`, como los otros
      evals.
- [x] 5.4 **Flag en `false`.** Medido: 4 casos anotados (hacen falta 20) y
      recall@12 del 56%. El veredicto está en `evals/TRANSACTION_TABLES_EVAL.md`.
      Dos hallazgos que bloquean: `CA001` no es un `document_id` del corpus —
      existen `CA001A`, `CA001M`, `CA001k`, `SCA001`— y en `CA048` la tabla
      `POLICY` cae en la posición 15, fuera del tope de 12.

## 6. Contrato y cierre del servicio

- [x] 6.1 `AnswerResponse.business_db` ya existe; extender `CodeResolution` con
      las tablas por dependencia en `app/generation/rag/schemas.py`. Schemas
      Pydantic con `Field(description=...)` bilingüe, nunca `dict`.
- [x] 6.2 `app/api/business_db.py`: cada corrida listada dice si tiene aristas y
      de cuándo. Router delgado — el conteo vive abajo.
- [x] 6.3 `GET /config`: declarar el paso de anclaje de base en `flow`, para que
      `/agents/flow` lo pueda dibujar sin constantes locales.
- [x] 6.4 Tests de contrato en `tests/api/`: la lista de corridas lleva el estado
      de aristas y distingue «build con 0 aristas» de «sin build»; `GET /config`
      declara el paso y NO lo mete como nodo ni como arista del grafo.
- [x] 6.5 `pytest` (1.058 passed) y `ruff check .` en verde desde `ai-service/`;
      `pnpm test` (28), `eslint` y `pnpm build` en verde desde `business-backend/`.
- [x] 6.6 **Sin cambios de ruta.** `/business-db/runs` y `/config` ganan campos,
      no endpoints; `app-routes.md` no se toca.

## 7. Consola

- [x] 7.1 `business-backend/lib/ai-service/types.ts`: `BusinessDbContext`,
      `CodeResolution`, `DependencyTable` y el vocabulario de roles y causas. Es
      el espejo del contrato, no una re-declaración libre.
- [x] 7.2 Turno de respuesta: la cadena `código → rutinas → tablas (rol)`,
      colapsada por defecto, con corrida y ambiente.
- [x] 7.3 Aviso de contexto incompleto con sus causas, al mismo peso visual que el
      de evidencia recortada. Una causa no mapeada se muestra con su nombre.
- [x] 7.4 `business-db-console.tsx`: estado de aristas por corrida y confirmación
      al activar una corrida sin aristas, sin bloquearla.
- [x] 7.5 `/agents/flow`: el paso de anclaje, tomado de `config.flow`. Si el
      servicio no lo declara, no se dibuja.
- [x] 7.6 Tests de la consola según `bff-standards.md` y `frontend-standards.md`;
      `pnpm lint` y `pnpm build` en verde desde `business-backend/`.

## 8. Specs

- [x] 8.1 Los deltas de `business-db-context` y `web-console` de este change
      reflejan lo implementado; corregirlos si la implementación se apartó.
- [x] 8.2 `python scripts/validate_specs.py` sin errores.
- [x] 8.3 Anotado en `openspec/domain/visualtime-database-metadata.md` §5.3: las
      cifras por corrida (561 / 1.556, y 460 / 957 con las guardas), la colisión
      de códigos por substring, la trampa del prefijo verbal que fabrica
      `SCA001`, y que `CA001` no es un `document_id`. Con su marca de evidencia.
- [x] 8.4 `add-business-db-context` se archiva **antes** que este change.
  **2026-09-12**: archivado como `2026-09-11-add-business-db-context`, y sus
  deltas integrados en `specs/business-db-context/` antes que los de acá.

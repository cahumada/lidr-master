# Implementation Tasks

Los grupos 1 a 6 van en `add-dependency-table-anchoring-ai-service`. El grupo 7 va
en `add-dependency-table-anchoring-web`, después de que el contrato mergee.

## 1. Persistencia de las aristas

- [ ] 1.1 `TransactionTableEdge` en `ai-service/app/generation/rag/store/models.py`:
      identidad `(tenant, env, run_id, transaction_code, table_name)`, más
      `role`, `role_reason`, `via_routines` (lista), `fan_in`, `origin`,
      `created_at`. Índice por `(tenant, env, run_id, transaction_code)` — la
      lectura es siempre por código. Va por `run_id` del mirror, **no** por
      `doc_version`.
- [ ] 1.2 Migración Alembic para esa tabla. No reformatear `alembic/versions/`.
- [ ] 1.3 Tabla de estado por corrida (o columna derivable) que responda «¿esta
      corrida tiene aristas?» sin contar filas en cada request.
- [ ] 1.4 Sumar la tabla al inventario de `app/ingestion/pipeline.py` si el
      `reset` la tiene que contemplar; si no corresponde, dejarlo escrito acá.

## 2. Armado de las aristas (sin I/O de red, testeable)

- [ ] 2.1 `app/generation/rag/business_db/roles.py`: las reglas ordenadas
      `(patrón, rol)` de `design.md` §3.1 como datos, y `classify_role()` puro que
      devuelve `(role, reason)` — `unknown` con razón cuando ninguna aplica.
      Sin I/O.
- [ ] 2.2 `app/generation/rag/business_db/dependencies.py`: el salto por nombre con
      guarda de largo ≥ 5 y desambiguación por munch máximo, y el salto por
      dependencia. Funciones puras sobre listas de códigos, nombres y aristas —
      la lectura del mirror queda afuera.
- [ ] 2.3 El umbral de fan-in sale de `app/config.py` con default medido, nunca de
      una constante en el módulo.
- [ ] 2.4 Tests en `tests/generation/rag/business_db/test_dependencies.py`:
      `CA013` / `CA013A` (munch máximo), `AG001` / `AG001_K` / `MAG001`, código de
      largo 4, código sin rutinas, rutina sin tablas.
- [ ] 2.5 Tests en `tests/generation/rag/business_db/test_roles.py`: un caso por
      regla de §3.1, el orden destino-antes-que-camino, y `unknown` con razón.

## 3. El batch

- [ ] 3.1 `ai-service/scripts/build_transaction_tables.py` con `--dry-run`, con el
      mismo patrón que `build_process_map.py`: lee `chunks` (los `document_id`),
      `business_dependencies` y `business_tables` de una corrida, arma las aristas
      con rol, y las persiste con `ON CONFLICT DO NOTHING`.
- [ ] 3.2 Reporte de la corrida: documentos anclados, pares código–rutina, aristas
      por rol, ambigüedades resueltas por munch máximo, tablas sin ficha en el
      diccionario. Se escribe al lado del artefacto, como hace el mapa de procesos.
- [ ] 3.3 Correrlo contra `20260909_214921` y dejar las cifras en el reporte.
      Comprobar contra lo medido al planear: 554 documentos llegan a ≥ 1 tabla,
      55 pares ambiguos sobre 31 documentos.

## 4. Lectura y bloque

- [ ] 4.1 `DependencyTable`, el `Literal` de roles y las causas nuevas
      (`edges_not_built`, `no_dependency_routine`, `routine_without_tables`,
      `code_too_short_to_anchor`, `dependency_tables_capped`, `role_unknown`) en
      `app/generation/rag/business_db/models.py`. Repartirlas entre
      `DECLARED_ABSENT` e `INCOMPLETE_OUTCOMES` según §6 del proposal:
      `edges_not_built` y `dependency_tables_capped` son incompletitud; el resto,
      ausencia declarada.
- [ ] 4.2 `reader.py`: lectura de `transaction_table_edges` por código y corrida,
      y el chequeo de «esta corrida tiene aristas» que emite `edges_not_built`.
- [ ] 4.3 `render.py`: la sección nueva, ordenada por rol, con las rutinas de cada
      tabla; y el orden de recorte de §5 del diseño, con `core` / `historical` /
      `validation` / `message` y las rutinas fuera del recorte.
- [ ] 4.4 `app/foundation/prompts/answer/v3/user.j2`: la sección, con
      `StrictUndefined`. Sin `v4`.
- [ ] 4.5 Tope de tablas por código y flag de habilitación en `app/config.py` y
      `ai-service/.env.example`. El flag arranca **apagado** hasta el grupo 5.
- [ ] 4.6 Tests de render: orden por rol, recorte en el orden declarado, una tabla
      nunca pierde sus rutinas, `dependency_tables_capped` con el conteo real.
- [ ] 4.7 Test de que `v1` y `v2` siguen renderizando byte a byte.

## 5. Medición (bloquea la habilitación)

- [ ] 5.1 `ai-service/evals/golden_transaction_tables.json` con ~20 transacciones
      anotadas por el dueño del repo. Semilla verificada al planear: `CA014` →
      `COVER`; `CA025` → `ROLES`, `CLIENT`; `CA001` y `CA048` → `POLICY`,
      `CERTIFICAT`, `POLICY_HIS`.
- [ ] 5.2 `ai-service/scripts/eval_transaction_tables.py`: precisión y recall de
      `core`, recall del conjunto entero, y tasa de `unknown`. Mismo formato de
      reporte que `eval_retrieval.py`.
- [ ] 5.3 Correrlo y dejar las cifras en `evals/` con su `.md`, como los otros
      evals.
- [ ] 5.4 Recién con ese número, decidir el default del flag de 4.5 y dejar la
      decisión escrita en el reporte.

## 6. Contrato y cierre del servicio

- [ ] 6.1 `AnswerResponse.business_db` ya existe; extender `CodeResolution` con
      las tablas por dependencia en `app/generation/rag/schemas.py`. Schemas
      Pydantic con `Field(description=...)` bilingüe, nunca `dict`.
- [ ] 6.2 `app/api/business_db.py`: cada corrida listada dice si tiene aristas y
      de cuándo. Router delgado — el conteo vive abajo.
- [ ] 6.3 `GET /config`: declarar el paso de anclaje de base en `flow`, para que
      `/agents/flow` lo pueda dibujar sin constantes locales.
- [ ] 6.4 Tests de contrato en `tests/api/`: la respuesta lleva las tablas con rol
      y rutinas; la lista de corridas lleva el estado de aristas; `GET /config`
      declara el paso.
- [ ] 6.5 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
- [ ] 6.6 `openspec/standards/app-routes.md`: sin cambios de ruta —
      `/business-db/runs` gana campos, no endpoints. Confirmarlo y dejarlo escrito.

## 7. Consola (rama `-web`, después del merge del contrato)

- [ ] 7.1 `business-backend/lib/ai-service/types.ts`: `BusinessDbContext`,
      `CodeResolution`, `DependencyTable` y el vocabulario de roles y causas. Es
      el espejo del contrato, no una re-declaración libre.
- [ ] 7.2 Turno de respuesta: la cadena `código → rutinas → tablas (rol)`,
      colapsada por defecto, con corrida y ambiente.
- [ ] 7.3 Aviso de contexto incompleto con sus causas, al mismo peso visual que el
      de evidencia recortada. Una causa no mapeada se muestra con su nombre.
- [ ] 7.4 `business-db-console.tsx`: estado de aristas por corrida y confirmación
      al activar una corrida sin aristas, sin bloquearla.
- [ ] 7.5 `/agents/flow`: el paso de anclaje, tomado de `config.flow`. Si el
      servicio no lo declara, no se dibuja.
- [ ] 7.6 Tests de la consola según `bff-standards.md` y `frontend-standards.md`;
      `pnpm lint` y `pnpm build` en verde desde `business-backend/`.

## 8. Specs

- [ ] 8.1 Los deltas de `business-db-context` y `web-console` de este change
      reflejan lo implementado; corregirlos si la implementación se apartó.
- [ ] 8.2 `python scripts/validate_specs.py` sin errores.
- [ ] 8.3 Anotar en `openspec/domain/visualtime-database-metadata.md` §5.3 las
      cifras medidas acá (561 documentos y 1.556 pares con guarda de largo ≥ 5
      sobre la corrida activa, contra los 578 / 1.622 que figuran hoy) y la
      colisión de códigos por substring, que §5.3 no registra. Con su marca de
      evidencia.
- [ ] 8.4 `add-business-db-context` se archiva **antes** que este change.

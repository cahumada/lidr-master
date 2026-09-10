## Why

El corpus contiene **574 documentos que describen transacciones que el sistema
fuente no contempla**, y el motor los recupera y los responde sin ninguna marca.

Medido sobre la corrida `20260909_214921` del mirror (`tenant=life_seguros`,
`env=PROD`) contra el corpus `DW Funtionals 2026.1` — detalle y consultas en
[visualtime-database-metadata.md](../../domain/visualtime-database-metadata.md):

| estado de la ventana | ventanas | con documento |
|---|---:|---:|
| `1` Activo | 1.765 | 954 |
| `3` Acceso restringido | 1.588 | **570** |
| `2` En proceso de instalación | 18 | **4** |
| `4` (error de datos, se trata como `3`) | 18 | 0 |

`WINDOWS.SSTATREGT` declara ese estado y **el sistema solo contempla el valor
`1`**. Son 1.624 de 3.389 ventanas (48%) que existen en la base pero no operan.
El árbol que consume el servicio no lo distingue, porque `windows_tree.csv`
tiene cinco columnas y `SSTATREGT` no es una de ellas.

El efecto es una respuesta que afirma de más: el motor describe cómo funciona
una transacción a la que hoy no se puede acceder, con la misma seguridad que una
vigente, y sin que quien lee tenga forma de saberlo. Es la clase de defecto que
las reglas del repo prohíben explícitamente — afirmar sin evidencia sobre reglas
de negocio de seguros.

El insumo para arreglarlo ya está cargado: `visualtime.business_data` tiene las
3.389 filas de `WINDOWS` con su `SSTATREGT`.

## What Changes

- `ChunkMetadata` gana `window_status`: el **estado declarado por el catálogo**
  (`Activo`, `Acceso restringido`, `En proceso de instalación`), no un booleano
  nuestro. `TABLE26` es la fuente de los nombres; `4` se normaliza a `3` con un
  warning; un valor desconocido o ausente queda **no resuelto**.
- `NavigationTree` aprende a resolver el estado de un código, y se le suma un
  segundo loader que lo arma **desde el mirror en Postgres** (`WINDOWS` de la
  corrida fijada) además del CSV existente.
- Qué fuente gana lo decide un setting explícito, como ya hace `CORPUS_BUCKET`
  con el corpus: si `BUSINESS_DB_RUN_ID` está puesto, gana el mirror; si no, el
  CSV. La corrida **se elige**, nunca "la más reciente".
- `render_hit_block` agrega una línea de advertencia **solo cuando el estado no
  es `Activo`**. Un hit vigente o no resuelto se renderiza byte a byte igual que
  hoy, así el eval de fidelidad sigue siendo comparable.
- Un script de backfill estampa el estado en los chunks ya cargados con un
  `UPDATE` de metadata. **No hay rebuild ni re-embedding**: el vector no depende
  de este campo, y la clave física del chunk tampoco.

Fuera de alcance, a propósito:

- **Un filtro `window_status` en `/search`.** Excluir lo no contemplado es una
  decisión de producto que necesita la consola web (otro repo, otro playbook).
  Este change hace que el modelo y el lector lo **sepan**; ocultar es después.
- **Aplicar el mismo criterio a otras tablas del mirror.** El catálogo de estados
  es por tabla y `WINDOWS` no declara el suyo — ver el `[HIPÓTESIS]` de §4.2 del
  documento de dominio.

## Capabilities

### Modified Capabilities

- `chunk-schema`: la metadata lleva el estado declarado de la ventana, con la
  misma regla de "ausente = no resuelto" que el resto de los campos opcionales.
- `document-chunking`: el chunker estampa ese estado cuando el árbol lo resuelve.
- `retrieval`: un hit declara el estado, y el bloque de evidencia lo advierte
  cuando la transacción no está contemplada.

## Impact

- `ai-service/app/generation/rag/navigation.py` — catálogo de estados,
  `NavigationLocation.window_status`, resolución y normalización de `4`→`3`,
  loader desde Postgres.
- `ai-service/app/generation/rag/schemas.py` — `ChunkMetadata.window_status` y
  `SearchHit.window_status`.
- `ai-service/app/generation/rag/store/models.py` — columna `window_status`.
- `ai-service/alembic/versions/` — migración de la columna.
- `ai-service/app/generation/rag/store/repository.py` — la columna viaja en el
  hit.
- `ai-service/app/generation/rag/chunking/functional_spec.py` — estampado.
- `ai-service/app/generation/rag/context_budget.py` — advertencia en
  `render_hit_block`.
- `ai-service/app/config.py` — `BUSINESS_DB_ENV`, `BUSINESS_DB_RUN_ID`.
- `ai-service/app/dependencies.py` — qué loader se usa.
- `ai-service/scripts/backfill_window_status.py` — nuevo.
- `ai-service/tests/generation/rag/`, `tests/store/` — tests.

## Backfill medido (2026-09-09)

Corrida `20260909_214921`, `tenant=life_seguros`, `doc_version=DW Funtionals 2026.1`.
Script `scripts/backfill_window_status.py` sobre la base de Railway:

| estado resuelto | chunks |
|---|---:|
| Activo | 21.352 |
| Acceso restringido | 20.995 |
| En proceso de instalación | 338 |
| (sin resolver) | 13.852 |

- Documentos en el corpus: 2.176; sin ventana que matchee estado: 666.
- Normalizaciones `4`→`3` en la carga del árbol: 18.
- Filas actualizadas: 56.537 (idempotente: segunda corrida deja los mismos conteos).

## Eval de fidelidad (después del backfill)

`uv run python scripts/eval_generation.py --source curated --skip-llm` sobre
36 preguntas curadas (incluye la nueva `U-MGSL006-acceso-restringido`):

- `citation_coverage`: **97%** (35/36; el miss `U-CO001-unit-linked-documentos`
  ya existía antes de este change — recuperación, no renderizado de estado).
- `grounded_rate`: 100%
- `U-MGSL006-acceso-restringido`: **covered=True** — la transacción con acceso
  restringido entra en las citas recuperadas.

No se guardó corrida `--skip-llm` previa al backfill en la misma base; las
preguntas que no tocan ventanas no contempladas mantienen el mismo resultado de
cobertura de citas porque `render_hit_block` no cambia para hits activos o sin
estado resuelto.

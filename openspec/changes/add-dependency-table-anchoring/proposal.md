## Why

El bloque de base que aterrizó con `add-business-db-context` ancla por
`WINDOWS.NG_IDENTI`, y esa columna **solo declara algo para las ventanas de tipo
10**: los catálogos `MAnnnn` ↔ `TABLE<n>`. Medido contra la corrida activa
`20260909_214921`, para las transacciones de negocio reales no declara nada:

| código | `NG_IDENTI` |
|---|---|
| `CA001` | `NULL` |
| `CA014` | `0` |
| `CA025` | `0` |
| `CA048` | `0` |

O sea: para *"¿qué tablas toca `CA014`?"* —la pregunta que un analista funcional
hace todo el día— el bloque de base hoy **no aporta una sola tabla**. Responde
sobre catálogos y calla sobre el negocio.

La pregunta tampoco se contesta leyendo el texto del chunk. Esa vía está medida
en [visualtime-database-metadata.md §5.2](../../domain/visualtime-database-metadata.md):
563 de 2.411 tablas aparecen nombradas literalmente en el corpus, con el caveat
abierto de que el token de 4+ caracteres mete `TRACE` y `LEVELS` por ser palabras
corrientes. Y §5.4 es explícito: una coincidencia de nombre es **indicio**, no
hecho, y no puede viajar como *"`CA014` usa `PREMIUM_MO`"*.

**Lo que sí es un hecho declarado está cargado y sin usar.**
`visualtime.business_dependencies` tiene, en la corrida activa, **91.025 aristas,
49.271 de ellas hacia `target_type='TABLE'`**, entre **10.988 rutinas** y **1.906
tablas** — de las cuales **1.658 tienen ficha en `business_tables`**. Son las
dependencias que Oracle compiló, no una inferencia sobre nombres. El servicio no
lee esa tabla.

El puente entre el corpus y ese grafo es el único salto que usa nombres, y está
medido (§5.3): el `document_id` contenido en el nombre del objeto Oracle. Con la
guarda de largo ≥ 5 sobre los 2.176 documentos del corpus da **561 documentos y
1.556 pares**, y **554 documentos llegan a por lo menos una tabla**.

Verificado contra las cuatro transacciones que el dueño del repo anotó a mano:

| código | rutinas | tablas esperadas | resultado |
|---|---|---|---|
| `CA014` | `INSCA014PKG`, `INSPOSTCA014`, `INSVALCA014DB01/02/03`, `INSCOPYCA014`, `REACA014` | `COVER` | ✅ |
| `CA025` | `INSPOSTCA025PKG`, `INSROLES_CA025`, `INSVALCA025ALL/UPD`, `REACA025B` | `ROLES`, `CLIENT` | ✅ |
| `CA001` | `INSCA001PKG`, `INSCA001MPKG`, `INSPOLICYCA001`, `REAPREMIUM_CA001`, … | `POLICY`, `CERTIFICAT`, `POLICY_HIS` | ✅ |
| `CA048` | `INSEXECUTECA048`, `INSPRECA048` | `POLICY`, `CERTIFICAT`, `POLICY_HIS` | ✅ |

Recall completo. **El problema es el otro**: `CA014` llega a **38 tablas** y la
que el analista llama core es una. La distribución sobre los 554 documentos es
mediana 8, p90 22, máximo 185, promedio 10,9. Volcar eso al prompt sin ordenar
cambia un bloque que no dice nada por uno que dice demasiado — y las dos formas
hacen que el modelo afirme mal.

Y hay una tercera pata que hoy nadie ve: **el servicio ya devuelve `business_db`
en `AnswerResponse` y la consola lo tira**. `lib/ai-service/types.ts` no tiene el
campo y ninguna pantalla lo muestra. El operador no puede saber si una respuesta
se apoyó en la base, de qué corrida, ni qué quedó afuera. Con este change eso pasa
de ser una omisión a ser un defecto: la cadena `código → rutinas → tablas` es
justamente lo que hace auditable la respuesta.

## What Changes

- **Las aristas se materializan en batch, no se resuelven por request.** Nueva
  tabla `transaction_table_edges` y `scripts/build_transaction_tables.py`, con el
  mismo patrón que `process_map_edges` y `build_process_map.py`. Dos motivos, los
  dos en `design.md`: el salto por nombre es un `LIKE '%CODE%'` contra 10.988
  nombres —comodín inicial, sin índice posible—, y la desambiguación necesita el
  universo entero de códigos, que en un request no está.
- **La ambigüedad del salto por nombre se resuelve por munch máximo.** Medido:
  **184 `document_id` de largo ≥ 5 son substring de otro** (`CA013` ⊂ `CA013A`,
  `AG001` ⊂ `AG001_K` y `MAG001`), y eso produce **55 pares código–rutina
  ambiguos sobre 31 documentos** — `INSPOSTCA013A` es de `CA013A`, no de `CA013`.
  Gana el código más largo que matchea; el corto no se lleva esa rutina.
- **Cada arista lleva su rol, derivado de reglas ordenadas y auditables**, con el
  mismo patrón que `taxonomy.py`: datos `(patrón, rol)`, no ramas de código. El
  vocabulario es cerrado —`reference`, `historical`, `message`, `validation`,
  `unknown`— y un caso que no matchea ninguna regla es `unknown` **con su razón**,
  nunca un default. Las señales del destino (la ficha en `business_tables`:
  `TABLE<n>` y *(Contenido fijo)* → referencia; `_HIS` e *"Historia de…"* →
  histórica; `MESSAGE` / `WIN_MESSAG` → mensajes) le ganan a las del camino
  (alcanzada solo por `INSVAL*` → validación).
- **No hay rol `core`, y eso es un resultado de medición, no un recorte.** El
  plan original lo iba a derivar de un fan-in bajo. Medido contra las cuatro
  transacciones anotadas, esa regla **corre al revés**:

  | código | tabla anotada | fan-in | tabla NO anotada | fan-in |
  |---|---|---:|---|---:|
  | `CA014` | `COVER` | 1.037 | `NOPAYROLL` | 44 |
  | `CA025` | `CLIENT` | 1.925 | `CLIALLOPRO` | 42 |
  | `CA001` | `CERTIFICAT` | 1.989 | `CUR_ALLOW` | 30 |

  Una póliza, un certificado y un cliente los toca casi todo el sistema
  **porque** son las entidades centrales: la rareza indica periférico, no
  central. Ninguna otra señal declarada los aísla tampoco. Afirmar `core` sobre
  cuatro puntos anotados sería la calibración manual que este repo evita en
  `retrieval`. El fan-in **se guarda en cada arista** para poder revisarlo, y no
  se usa para degradar nada.
- **El orden es la cobertura: cuántas rutinas de la transacción llegan a cada
  tabla, sobre cuántas tiene.** Dos conteos declarados divididos, sin umbral que
  calibrar — es lo que hace que sirva como orden sin afirmar una jerarquía.
- **El rol `unknown` es la mayoría y se declara así.** Construido contra la
  corrida activa: **4.939 de 5.907 aristas (84%)** quedan `unknown`. El bloque lo
  dice con todas las letras —*"la transacción toca la tabla, pero en qué carácter
  no está declarado. No lo supongas."*— en vez de inventarles un rol.
- **Se mide contra un set anotado antes de entrar al prompt.** Las cuatro
  transacciones anotadas por el dueño son la semilla; el change las lleva a ~20 en
  `evals/golden_transaction_tables.json` y reporta **recall@N** —si la tabla que
  el analista nombra sobrevive al tope, que es lo único que decide si la respuesta
  la puede citar— más la posición bajo el orden por cobertura y la proporción de
  `unknown`. Sin 20 casos y 90% de recall el flag queda apagado.
- **El bloque de base gana una sección por código anclado** dentro de `v3` — no
  hay `v4` ni cambio de plantilla: la sección es contenido del bloque que
  `business-db-context` ya gobierna y que `render.py` compone. Las tablas entran
  ordenadas por cobertura, y la declaración de cada una dice **por qué rutinas**
  entró, para que la respuesta pueda citarlo.
- **El vocabulario de completitud se extiende**, siempre cerrado y sin cajón de
  sastre: `edges_not_built`, `no_dependency_routine`, `routine_without_tables`,
  `code_too_short_to_anchor`, `dependency_tables_capped`, `role_unknown`. El
  primero es el que importa operativamente — activar una corrida cuyas aristas
  nunca se construyeron no puede degradar la respuesta en silencio.
- **`NG_IDENTI` no se toca.** Sigue siendo el camino del tipo 10 y las dos vías
  conviven: son autoridades distintas sobre cosas distintas.
- **La consola refleja el flujo real.** Tres pantallas: el turno de respuesta
  muestra la cadena `código → rutinas → tablas (rol)` con lo que no se pudo traer
  y su causa; `/business-db` dice si la corrida activa tiene aristas construidas y
  cuándo, porque hoy se puede activar una corrida que deja el bloque mudo; y
  `/agents/flow` declara el anclaje de base como un paso de la resolución, que es
  lo que esa pantalla existe para mostrar.

Fuera de alcance, con su motivo:

- **Las tablas nombradas en el texto del chunk** (§5.2). Sigue con el hueco de
  medición del token de 4 caracteres abierto. Entra cuando se cierre, y entra como
  indicio marcado.
- **Reconocimiento de entidades sobre la pregunta.** Una tabla que ningún hit
  ancla sigue sin entrar. Es lo que habilitaría responder sobre las ~655
  transacciones sin documento funcional, y es un change propio.
- **Las rutinas de largo ≥ 7 donde el `document_id` *es* el objeto Oracle** (§5.3,
  355 pares). Son identidad, no inferencia, y la hipótesis de que son las que
  `taxonomy.py` marca `interface` sigue sin contrastar contra `transaction_type`.
- **Dirección de la dependencia (lee / escribe).** `dependency_type` vale `HARD`
  en las 182.050 filas y `metadata` está vacío: el dato no está en el mirror.
  Derivarlo exigiría el código fuente de las rutinas, que el snapshot deja como
  `.sql` sin cargar.

## Capabilities

### Modified Capabilities

- `business-db-context`: el bloque gana un segundo camino de anclaje —el grafo de
  dependencias de Oracle— con su rol por tabla, su desambiguación y sus causas de
  incompletitud.
- `web-console`: la consola muestra de dónde salió el contexto de base de una
  respuesta, y avisa cuando la corrida activa no tiene aristas construidas.

## Impact

**Precondición de secuencia.** `add-business-db-context` está implementado pero
**sin archivar**: su capability vive todavía en `openspec/changes/`. Los deltas de
acá se apoyan en esos requirements. Si este change se archiva primero, la
capability queda incoherente.

**Dos ramas.** El plan vive en `add-dependency-table-anchoring-ai-service`. El
grupo 7 (consola) sale en `add-dependency-table-anchoring-web`, después de que el
contrato haya mergeado — es lo que pide
[git-workflow.md](../../standards/git-workflow.md).

- `ai-service/app/generation/rag/business_db/dependencies.py` — nuevo: el armado
  de aristas desde el mirror y la desambiguación por munch máximo.
- `ai-service/app/generation/rag/business_db/roles.py` — nuevo: las reglas
  ordenadas `(patrón, rol)` y el `unknown` con razón. Sin I/O.
- `ai-service/app/generation/rag/business_db/models.py` — `DependencyTable`, el
  vocabulario de roles, las causas nuevas.
- `ai-service/app/generation/rag/business_db/reader.py` — lectura de
  `transaction_table_edges` por código, con su índice.
- `ai-service/app/generation/rag/business_db/render.py` — la sección nueva y su
  lugar en el orden de recorte.
- `ai-service/app/generation/rag/store/models.py` — `TransactionTableEdge`.
- `ai-service/alembic/versions/` — la migración de esa tabla.
- `ai-service/scripts/build_transaction_tables.py` — el batch, con `--dry-run`.
- `ai-service/app/foundation/prompts/answer/v3/user.j2` — la sección.
- `ai-service/app/api/business_db.py` — el estado de aristas de cada corrida.
- `ai-service/evals/golden_transaction_tables.json`,
  `ai-service/scripts/eval_transaction_tables.py` — el set anotado y su medición.
- `ai-service/tests/generation/rag/business_db/`, `ai-service/tests/api/` — tests.
- `business-backend/lib/ai-service/types.ts` — `BusinessDbContext` y
  `DependencyTable` del lado TypeScript.
- `business-backend/app/(console)/…/answer/` — la cadena en el turno.
- `business-backend/app/(console)/(admin)/business-db/business-db-console.tsx` —
  el estado de aristas por corrida.
- `business-backend/app/(console)/(admin)/agents/flow/` — el paso de anclaje.

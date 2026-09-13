## Why

> **Estado: propuesto y diferido.** Este change no se implementa antes de la
> entrega final. Se documenta para no perder el razonamiento — y sobre todo para
> dejar escrita su precondición, que es un trabajo separado y más barato.
> || **Status: proposed, deferred.** Documented, not scheduled.

El contexto de base hoy es **push**: `resolve_context` elige las tablas antes de
que exista el prompt, y `render_block` las poda hasta entrar en el presupuesto.
El modelo recibe un bloque cerrado y no tiene forma de pedir lo que falta.

Esa elección se apoya en una sola señal: que el código de transacción aparezca
**textualmente** en un hit del corpus (`anchored_codes`, con
`MIN_ANCHOR_LENGTH = 5`). Es una señal buena — `add-dependency-table-anchoring`
la midió con recall completo sobre las cuatro transacciones anotadas — pero es
la única. Cuando la pregunta nombra una tabla que ningún hit ancla, el bloque
calla, y el vocabulario de `INCOMPLETE_OUTCOMES` sirve para *declarar* el hueco,
no para cerrarlo. `add-dependency-table-anchoring` ya lo dejó fuera de alcance
con todas las letras: *"Una tabla que ningún hit ancla sigue sin entrar. […] es
un change propio."* Este es ese change.

El segundo hueco es el presupuesto. `render_block` recorta por `DROP_ORDER` sin
saber qué necesita la pregunta: tira filas y tablas en un orden fijo, no en el
orden de lo que el turno iba a usar. Un recorte declarado es mejor que uno mudo,
pero sigue siendo ciego.

**Lo que este change NO es.** No es un reemplazo del anclaje. Es una segunda vía
que solo corre cuando la primera dejó un hueco, y el camino por defecto sigue
siendo el bloque determinista de hoy.

## What Changes

- **Una tool `describe_table(name)` expuesta al sintetizador**, que devuelve la
  ficha de una tabla —columnas, descripciones, tablas relacionadas por el grafo
  de dependencias— leyendo por `read_table_dictionary_full`. **La misma función
  que ya alimenta `render_block`**: cambia quién decide cuándo llamarla, no qué
  devuelve. El modelo emite la intención; el servicio ejecuta la lectura.
- **El bucle de tool use vive donde hoy está el sintetizador**, con tope de
  vueltas y tope de tablas por turno. Mientras la respuesta traiga `tool_use`, el
  servicio ejecuta, adjunta el `tool_result` al historial y vuelve a llamar.
- **`LLMClient` deja de ser de un solo disparo.** Hoy el protocolo `LLM` es
  `complete(system, user) -> Completion`: dos strings, sin historial y sin tools.
  El bucle necesita una lista de mensajes y un array de tools, en las dos
  implementaciones (`AnthropicChatLLM` y `OpenAICompatibleChatLLM`). Es el cambio
  estructural más grande del change y el que más superficie toca.
- **El bloque empujado se achica, no desaparece.** Sigue entrando el anclaje por
  código con su sección de dependencias; lo que se recorta por presupuesto pasa a
  ser recuperable por tool en vez de perderse. `dropped_by_budget` gana sentido:
  declara qué quedó afuera *y* sigue disponible a pedido.
- **El inspector muestra la traza de tool calls.** `/agents/flow` y el turno de
  respuesta hoy muestran un bloque estático; con el bucle hay que mostrar qué
  tablas pidió el modelo, en qué vuelta y con qué resultado. Sin eso, el change
  rompe la transparencia que `add-prompt-inspection` acaba de construir.
- **Causa nueva, cerrada como las demás**: `tool_budget_exhausted` — el modelo
  pidió más tablas que el tope de vueltas. Es una ausencia declarada, igual que
  `dependency_tables_capped`.
- **No se abre un servidor MCP.** MCP es el mismo protocolo de tool use con un
  transporte estándar encima; paga cuando la capacidad la consumen otros
  clientes. Acá el único consumidor es `ai-service`. Ver `design.md` §3.

Fuera de alcance, con su motivo:

- **Tools de consulta de datos** (`SELECT` contra la base de negocio). La ficha
  de una tabla es metadato declarado; una fila es dato de un cliente. Otra
  conversación entera, con otra superficie de riesgo.
- **Tool use en `evidence_retriever`.** `search_corpus` ya corre determinista y
  eso no duele hoy. Un change que mezcle las dos vías no se podría medir por
  separado.

## Capabilities

### Modified Capabilities

- `business-db-context`: el contexto de base gana una segunda vía, *pull*, para
  las tablas que el anclaje textual no alcanza.
- `web-console`: el inspector muestra la traza de tool calls del turno, no solo
  el bloque que se empujó.

## Impact

**Precondición dura.** Este change **no entra sin ampliar
`evals/golden_transaction_tables.json`**, que hoy tiene **4 casos**. El motivo
está en `design.md` §4 y es el que manda: con tool use, dos corridas del mismo
caso pueden pedir tablas distintas, así que la métrica pasa de un assert exacto a
varias corridas contra un umbral. Con cuatro casos, la varianza del modelo tapa
cualquier señal — no se podría demostrar que la tool mejora nada.

**Ampliar el set es trabajo separado y vale igual sin este change**: mide el
anclaje de hoy con más resolución. Hacerlo primero, y solo.

- `ai-service/app/foundation/llm/wrapper.py` — el protocolo `LLM` pasa a
  mensajes + tools; las dos implementaciones lo siguen.
- `ai-service/app/domain/graph/tools.py` — `describe_table` junto a
  `search_corpus`, con su esquema de entrada.
- `ai-service/app/domain/graph/agents/answer_synthesizer.py` — el bucle de tool
  use y sus topes.
- `ai-service/app/generation/rag/business_db/models.py` — `tool_budget_exhausted`
  y la traza de llamadas en `BusinessDbContext`.
- `ai-service/app/generation/rag/business_db/render.py` — el bloque empujado se
  achica; `dropped_by_budget` deja de ser terminal.
- `ai-service/app/domain/graph/inspector.py` — la traza expuesta a la consola.
- `ai-service/evals/golden_transaction_tables.json`,
  `ai-service/scripts/eval_transaction_tables.py` — set ampliado y medición por
  varias corridas.
- `business-backend/lib/ai-service/types.ts` y el turno de respuesta — la traza
  del lado TypeScript.

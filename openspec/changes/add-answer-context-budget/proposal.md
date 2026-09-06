## Why

Nadie cuenta tokens antes de llamar al proveedor. `build_context()`
(`app/generation/rag/prompt_builder.py`) concatena **todos** los hits que le
llegan, y `answer_synthesizer` los pasa tal cual a `llm.complete()`. No hay
presupuesto, no hay truncado, no hay aviso.

El tamaño real no es `limit`. `evidence_retriever` corre una búsqueda por
cada subconsulta y **une los hits deduplicando por `content_hash`**
(`app/domain/graph/agents/evidence_retriever.py`), así que el techo efectivo
es `limit × subconsultas`. Con `limit=10` —el default de la consola— y una
pregunta compuesta que el `decompose` parte en tres, el prompt puede llevar
30 chunks. Cada chunk narrativo está capado en `NARRATIVE_CHUNK_TOKEN_CAP`
= 500 tokens, así que el bloque de contexto va de ~5k a ~15k tokens sin que
cambie ningún knob visible.

**Medido sobre las 35 preguntas curadas** (base real, pipeline medido), no
estimado:

| Camino | Peor caso | % del presupuesto | Preguntas truncadas |
|---|---|---|---|
| `/answer` (una recuperación, `limit=10`) | 3.348 tokens | 20% | 0 |
| Agéntico (una búsqueda por subconsulta, unidas) | 6.701 tokens | 41% | 0 |
| Agéntico + memoria de conversación llena | 7.104 tokens | 43% | 0 |

El peor caso agéntico sale de una pregunta que el planner parte en **tres**
subconsultas, y duplica al del camino simple — la deduplicación por
`content_hash` evita que sea el triple. El default de 16.384 queda holgado
con 9.280 tokens de margen incluso con una sesión de conversación completa
encima, que es lo que hace que este change no pueda mover `citation_coverage`
sobre el golden set: ningún hit se descarta.

Con `gpt-4o-mini` (128k) eso no duele. El problema es que desde
`add-agent-profiles` el modelo del sintetizador es **configurable por
perfil** y multi-proveedor: un perfil apuntando a un modelo de ventana
chica desborda, y hoy el desborde se manifiesta como un error del proveedor
a mitad de la corrida agéntica —después de haber pagado el planner y la
recuperación—, con un mensaje que no dice cuál fue la causa. El fallo
depende de la forma de la pregunta, no de la configuración, que es la peor
clase de fallo: no se reproduce pidiendo la misma pantalla dos veces.

Hay una segunda razón, más de fondo. `AGENTS.md` §3 dice que nunca se borra
información de negocio en silencio. Recortar el contexto es exactamente
borrar información de negocio: si el chunk que respondía la pregunta quedó
afuera del prompt, la respuesta se degrada y hoy nada lo registraría. Un
presupuesto que descarta sin avisar sería un defecto nuevo, no una
solución — por eso el recorte tiene que ser **observable en la respuesta**,
no solo en un log.

El proyecto de referencia del curso ([`agents_event`](https://github.com/LIDR-academy/ai-engineering/blob/agents_event/ai-service/app/generation/rag/context_assembler.py))
resuelve esto con `truncate_to_token_budget()`: cuenta tokens sobre el chunk
**ya envuelto en su delimitador**, descarta chunks enteros desde la cola y
nunca parte uno al medio. Este change adapta ese patrón, con dos diferencias
que el dominio impone y que están en `design.md`: qué tokenizer se usa
cuando el proveedor no es OpenAI, y en qué orden se descarta cuando los hits
vienen de la unión de varias subconsultas.

## What Changes

- `ANSWER_MAX_CONTEXT_TOKENS: int = 16384` en `app/config.py`. Presupuesto
  del **bloque de contexto** —los chunks—, no del prompt entero: el system
  prompt y la persona son de tamaño acotado y conocido, la evidencia es la
  parte que crece con la pregunta.
- `app/generation/rag/context_budget.py` (nuevo): `fit_to_budget(hits,
  budget) -> BudgetedContext`, que devuelve los hits que entran, los que
  quedaron afuera y el costo en tokens. Cuenta sobre el bloque renderizado
  de cada hit (encabezado `[document_id · section]`, título, ruta y texto),
  no sobre `hit.text` pelado: los delimitadores son tokens que el modelo
  igual va a ver.
- Reusa `count_tokens()` de `app/generation/rag/chunking/base.py` en vez de
  instanciar un segundo encoder. Es el tokenizer de `text-embedding-3-small`
  y **no** el del modelo que responde: es una estimación con margen, no
  contabilidad exacta, y `design.md` explica por qué en un servicio
  multi-proveedor la contabilidad exacta no está disponible.
- El descarte es **por chunks enteros y desde el final**, nunca partiendo un
  chunk. Media regla de negocio es peor que una regla de negocio menos.
- Cuando la pregunta se dividió en subconsultas, el orden de descarte es
  **round-robin por subconsulta** en vez del orden de inserción actual: una
  pregunta compuesta no puede perder entera la evidencia de su segunda
  mitad porque la primera llenó el presupuesto. Justificado en `design.md`.
- `build_budgeted_messages()` compone presupuesto + prompt y devuelve
  `(system, user, BudgetedContext)`, así ningún camino de síntesis puede
  renderizar un prompt y olvidarse del presupuesto. `build_messages()` queda
  como el renderer crudo. `answer_synthesizer` propaga el recorte al estado
  del grafo.
- `AnswerResponse`, `AnswerAgenticResponse`, `AnswerAgenticProgress` y la
  respuesta **pausada** ganan `context_truncated: bool` y `dropped_hits:
  int` — la pausada también, porque un turno detenido en el gate muestra
  evidencia y mostrarla sin decir que está recortada es el mismo silencio.
  **`citations` pasa a ser lo que el modelo realmente vio**: hoy `citations`
  se llena con todos los hits recuperados, y con presupuesto activo eso
  citaría chunks que nunca entraron al prompt — una procedencia que no
  respalda nada.
- Log estructurado `answer_context_budgeted` —solo cuando hubo recorte— con
  `hits_in`, `hits_kept`, `hits_dropped`, `tokens_used`, `budget` y
  `dropped_document_ids`: qué documentos quedaron afuera, no solo cuántos.
- Sin presupuesto configurado a `0` o negativo: se rechaza en el arranque
  (`Settings` con `ge=1`), no se interpreta como «sin límite». Un `0` que
  vacía el contexto en silencio es el mismo defecto que este change viene a
  cerrar.

**Deliberadamente afuera (no de este change):**

- Derivar el presupuesto del modelo del perfil. Requiere una tabla de
  ventanas por modelo que hoy no existe y que se desactualiza sola; un
  setting global conservador cubre el caso real sin inventar ese registro.
- Reintentar con menos chunks cuando el proveedor igual rechaza por
  longitud. Con el presupuesto puesto deja de ser el camino esperado.
- Contar tokens del system prompt y la persona. `AGENT_PERSONA_MAX_CHARS`
  ya acota la parte variable; meterlas al presupuesto haría que cambiar la
  persona mueva cuánta evidencia entra, que es un acople peor que el margen
  que ahorra.
- Recorte del historial conversacional: no hay historial. Eso es
  `add-conversation-memory`, que consume este presupuesto y no lo redefine.

## Capabilities

### New Capabilities
(ninguna — el presupuesto es una regla nueva sobre una capability que ya
existe.)

### Modified Capabilities
- `answer-generation`: el bloque de contexto tiene un techo en tokens, el
  recorte se reporta en la respuesta, y `citations` pasa a ser la evidencia
  que entró al prompt y no la que devolvió el retriever.

## Impact

- `ai-service/app/generation/rag/context_budget.py` (nuevo)
- `ai-service/app/generation/rag/prompt_builder.py` — `build_messages`
  aplica el presupuesto y reporta el recorte.
- `ai-service/app/generation/rag/schemas.py` — `context_truncated`,
  `dropped_hits` en `AnswerResponse`.
- `ai-service/app/generation/rag/answer.py` — propaga los campos nuevos.
- `ai-service/app/domain/graph/agents/answer_synthesizer.py` — `citations`
  pasa a ser lo presupuestado; contribución con el recorte.
- `ai-service/app/domain/schemas.py` — `AnswerAgentState` lleva el recorte.
- `ai-service/app/api/answer_agentic.py` — expone los campos nuevos.
- `ai-service/app/config.py` — `ANSWER_MAX_CONTEXT_TOKENS`.
- `ai-service/.env.example` — documenta el knob.
- `ai-service/tests/generation/rag/test_context_budget.py` (nuevo)
- `ai-service/tests/generation/rag/test_prompt_builder.py`
- `ai-service/tests/domain/graph/agents/test_answer_synthesizer.py`
- `ai-service/tests/api/test_answer_router.py`
- `business-backend/lib/ai-service/types.ts` — campos nuevos del contrato.
- `business-backend/app/answer/answer-console.tsx` — avisa cuando la
  respuesta se construyó con evidencia recortada.
- `ai-service/README.md` — el knob y qué significa el aviso.
- `openspec/changes/add-answer-context-budget/specs/answer-generation/spec.md`
  — delta; no se promociona a `openspec/specs/` hasta archivar.

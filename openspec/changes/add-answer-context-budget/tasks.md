# Implementation Tasks

## 1. Presupuesto y conteo

- [x] 1.1 `ANSWER_MAX_CONTEXT_TOKENS: int = 16384` en `app/config.py` con
      `Field(ge=1)` y comentario bilingüe que diga que es el presupuesto del
      **bloque de contexto**, no del prompt entero, y que el conteo es una
      estimación (tokenizer de embeddings, no del modelo que responde).
- [x] 1.2 Documentar el knob en `ai-service/.env.example`.
- [x] 1.3 `app/generation/rag/context_budget.py`: `render_hit_block(index,
      hit) -> str` (el bloque numerado tal como lo emite `build_context`) y
      `fit_to_budget(hits, budget) -> BudgetedContext` con `kept`, `dropped`,
      `tokens_used`, `budget`. Cuenta con `count_tokens()` de
      `chunking/base.py` — no instanciar un encoder nuevo.
- [x] 1.4 `build_context()` pasa a renderizar con `render_hit_block()` para
      que el texto contado y el texto enviado sean el mismo, verificado por
      un test y no por inspección.

## 2. Orden de descarte

- [x] 2.1 `evidence_retriever` conserva de qué subconsulta vino cada hit
      (acumulador por subconsulta antes de deduplicar). Un hit que
      encontraron dos subconsultas entra una sola vez, en la posición de la
      primera.
- [x] 2.2 `interleave_by_query()`, en el mismo módulo que `fit_to_budget`,
      intercala round-robin cuando hay más de un grupo; con cero o uno es la
      identidad. La llama `evidence_retriever`, que es donde existe el dato
      de qué subconsulta trajo cada hit.
- [x] 2.3 Test: pregunta compuesta con presupuesto que solo permite la mitad
      de los hits → sobrevive evidencia de **ambas** subconsultas.

## 3. Integración en la síntesis

- [x] 3.1 `build_budgeted_messages()` compone presupuesto + prompt y devuelve
      `(system, user, BudgetedContext)`. `build_messages()` queda como el
      renderer crudo para quien ya decidió qué mandar; los dos caminos de
      síntesis usan el compuesto.
- [x] 3.2 `answer_synthesizer` usa los hits presupuestados como `citations`
      y escribe `context_truncated` / `dropped_hits` en el estado.
- [x] 3.3 `AnswerAgentState` lleva los dos campos nuevos.
- [x] 3.4 Contribución de auditoría del sintetizador: el `summary` dice
      cuántos hits entraron de cuántos.
- [x] 3.5 Log `answer_context_budgeted` con `hits_in`, `hits_kept`,
      `hits_dropped`, `tokens_used`, `budget` y `dropped_document_ids` — qué
      documentos quedaron afuera, no solo cuántos. Se emite únicamente
      cuando hubo recorte.

## 4. Contrato y consola

- [x] 4.1 `context_truncated: bool` y `dropped_hits: int` en `AnswerResponse`,
      `AnswerAgenticResponse`, `AnswerAgenticProgress` **y**
      `AnswerAgenticPausedResponse`. La pausada también: un turno detenido en
      el gate muestra evidencia, y mostrarla sin decir que está recortada es
      el mismo silencio que el change viene a cerrar.
- [x] 4.2 `business-backend/lib/ai-service/types.ts` refleja los campos.
- [x] 4.3 `answer-console.tsx` muestra un aviso cuando
      `context_truncated` es true, con cuántos chunks quedaron afuera. Un
      recorte silencioso en la UI anula el propósito del change.

## 5. Tests

- [x] 5.1 `tests/generation/rag/test_context_budget.py`: presupuesto que
      entra completo; presupuesto que corta; un solo hit que ya excede el
      presupuesto (entra vacío, `dropped` lo reporta, no se parte el chunk);
      conteo sobre el bloque renderizado y no sobre `hit.text`.
- [x] 5.2 `test_prompt_builder.py`: `build_messages` con presupuesto chico
      emite solo los hits que entran, y el `context` renderizado coincide
      con lo contado.
- [x] 5.3 `test_answer_synthesizer.py`: `citations` == hits presupuestados,
      **no** los recuperados.
- [x] 5.4 `test_answer_router.py`: los campos nuevos viajan en la respuesta.
- [x] 5.5 Caso límite: presupuesto que no deja entrar ningún chunk → se
      comporta como «sin hits» (`INSUFFICIENT_CONTEXT_MESSAGE`, sin llamar
      al LLM), con `dropped_hits` > 0 para que se distinga de no haber
      recuperado nada.

## 6. Cierre

- [x] 6.1 `README.md` de `ai-service`: el knob, qué significa el aviso de
      recorte, y que el conteo es una estimación.
- [x] 6.2 `uv run python scripts/validate_specs.py`.
- [x] 6.3 `uv run pytest` y `uv run ruff check .` desde `ai-service/`.
- [x] 6.4 Confirmar que el presupuesto por default no mueve
      `citation_coverage`. Medido de forma DETERMINISTA en vez de con una
      corrida del eval: `--skip-llm` evita `generate_answer` y por lo tanto no
      ejerce el presupuesto, y correrlo con LLM cuesta 35 completions para
      responder algo que se puede demostrar. El presupuesto solo puede mover
      el número descartando un hit, así que alcanza con medir cuánto se
      acerca cada pregunta al techo.

      Resultado sobre las 35 curadas, **0 preguntas truncadas** en los dos
      caminos: `/answer` (una recuperación, `limit=10`) llega como mucho a
      3.348 tokens (20% del presupuesto); el agéntico, que es el que
      multiplica, a 6.701 (41%) desde una pregunta que el planner parte en
      tres subconsultas; y con una memoria de conversación llena encima,
      7.104 (43%), 9.280 tokens de margen. `citation_coverage` no puede
      moverse: ningún hit se descarta. Tabla completa en el proposal.

# Implementation Tasks

Depende de `add-answer-context-budget`: la memoria se recorta **dentro** del
presupuesto de contexto, así que ese change entra primero.

## 1. Modelo y persistencia

- [x] 1.1 `app/generation/conversation/models.py`: `ConversationFacts`
      (filtros activos, códigos mencionados, `document_id` citados en el
      último turno), `Turn` (pregunta escrita, pregunta resuelta, respuesta
      recortada, `created_at`) y `ConversationSession` (id, turnos, anchors,
      hechos, `created_at`, `updated_at`).
- [x] 1.2 `ConversationFacts.merge_with()`: escalares pisan, listas unen sin
      duplicados case-insensitive. Test del merge, incluido el caso de
      hechos vacíos en el primer turno.
- [x] 1.3 Migración alembic `conversation_sessions`. Confirmar que
      `include_name` de `alembic/env.py` no la excluye (excluye las tablas
      del checkpointer, no ésta).
- [x] 1.4 `store.py`: `create()`, `get()`, `save()`, `delete()` y
      `purge_expired()`. El `append_turn()` vive en el modelo, no en el
      store: recortar la ventana es una regla del dominio, no de la
      persistencia. Una sesión vencida por `CONVERSATION_SESSION_TTL_DAYS` se
      comporta como inexistente, no como error.
- [x] 1.5 Settings `CONVERSATION_MAX_TURNS = 4`,
      `CONVERSATION_MEMORY_MAX_TOKENS = 1024`,
      `CONVERSATION_SESSION_TTL_DAYS`, con comentario bilingüe. Documentar
      en `.env.example`.

## 2. Resolución de preguntas

- [x] 2.1 `resolver.py`: `resolve(question, facts) -> ResolvedQuestion` con
      la pregunta resuelta y qué referencia se sustituyó.
- [x] 2.2 Conservador por construcción: sin referente claro en los hechos,
      devuelve la pregunta **tal cual**. Test explícito de que no inventa.
- [x] 2.3 `query_planner` resuelve ANTES de `decompose`, y deja las dos
      preguntas en el estado.
- [x] 2.4 Test: «¿y para siniestros?» con `module_code` activo en los hechos
      produce una pregunta resuelta que el retriever puede buscar.
- [x] 2.5 Test: sin sesión, la pregunta resuelta es idéntica a la escrita y
      el camino es el actual, sin ramas nuevas.

## 3. Ventana, anchors y hechos

- [x] 3.1 Ventana deslizante de `CONVERSATION_MAX_TURNS` pares, descarte por
      pares completos.
- [x] 3.2 `anchors.py`: detector heurístico de restricciones fijadas por el
      usuario («solo módulo CA», «de acá en adelante ventanas de tipo X»).
      Sin llamada LLM.
- [x] 3.3 Un anchor se aplica como filtro por default en los turnos
      siguientes y **se muestra en la respuesta**. Un filtro aplicado en
      silencio es un defecto, no una comodidad.
- [x] 3.4 `facts.py`: actualización de hechos al cerrar el turno, a partir
      de los filtros usados y de los `document_id` citados. Sin llamada LLM
      extra: los hechos salen de lo que el turno ya produjo.

## 4. Presupuesto y prompt

- [x] 4.1 `budget.py`: recorte de la memoria dentro del presupuesto de
      contexto, con orden de descarte ventana → anchors → (hechos, nunca).
- [x] 4.2 Test: presupuesto ajustado → se recorta la memoria y **no** se
      pierde ni un chunk de evidencia.
- [x] 4.3 Prompt `answer/v2/{system,user}.j2` con el bloque de memoria,
      después de la persona y antes del contexto. `v1` no se toca.
- [x] 4.4 Test: ni la persona ni un turno anterior alteran la obligación de
      citar (mismo criterio que el test de persona de `add-agent-profiles`).

## 5. API y estado del grafo

- [x] 5.1 `AnswerAgentState` lleva `session_id`, `resolved_question` y
      `facts`.
- [x] 5.2 `app/api/answer_session.py`: `POST /answer/session`,
      `GET /answer/session/{id}`, `DELETE /answer/session/{id}`.
- [x] 5.3 `POST /answer/agentic/start` acepta `session_id` **opcional**.
      Test de que sin él el contrato y el comportamiento no cambian.
- [x] 5.4 La respuesta expone `resolved_question` y los hechos vigentes.
- [x] 5.5 `citation_validator` sigue validando contra los hits del turno
      actual. Test: un `document_id` citado en un turno anterior y ausente
      en éste NO cuenta como respaldo.
- [x] 5.6 La sesión se actualiza al cerrar el turno, incluido el camino que
      pasa por el gate de revisión humana.

## 6. Consola

- [x] 6.1 Crear la sesión en la PRIMERA pregunta —no al abrir `/answer`— y
      mandar `session_id` en cada turno. Perezoso a propósito: abrir la
      pantalla y cerrarla no debería dejar una fila. Si la creación falla, el
      turno sale igual sin memoria: degradado, nunca bloqueado.
- [x] 6.2 Mostrar la pregunta resuelta cuando difiera de la escrita.
- [x] 6.3 Mostrar los anchors vigentes y permitir quitarlos.
- [x] 6.4 «Empezar de nuevo» descarta la sesión (`DELETE`) y limpia los
      turnos en pantalla.
- [x] 6.5 `lib/ai-service/types.ts` refleja el contrato nuevo.

## 7. Verificación y cierre

- [x] 7.1 `uv run python scripts/validate_specs.py` -- 11 specs, 15 changes
      en curso, 0 errores y 0 advertencias.
- [x] 7.2 `uv run pytest` y `uv run ruff check .` desde `ai-service/` --
      **818 passed, 0 skipped** en 5:27 (con la base arriba, así que los tests
      de integración del store corrieron de verdad) y ruff limpio.
- [x] 7.3 Medir la tasa de FALSOS POSITIVOS del resolver sobre el golden
      set. La task decía «eval de fidelidad con memoria activa» y eso no es
      ejecutable: `scripts/eval_generation.py` llama a `generate_answer`, que
      es el camino de `POST /answer`, el que rechaza `session_id`. Lo que sí
      se puede medir con los datos que existen es el riesgo que nombra el
      `design.md`: las 35 preguntas son autocontenidas, así que con una sesión
      activa el número correcto de reescrituras es CERO y cualquier
      reescritura es un error.

      Encontró un defecto real: **3 de 35 (8,6%)** — «esos boletines», «esa
      cobranza», «ese pago», donde el demostrativo es determinante y no
      pronombre. Corregido con la regla gramatical (no con un umbral) y
      fijado con tests parametrizados en las dos direcciones. Después:
      **0 de 35**, y 0 reescrituras sin sesión.
- [ ] 7.6 (nuevo, NO de este change) Golden set multi-turno para medir el
      falso NEGATIVO y la calidad de la reescritura, más un eval que pase por
      el grafo en vez de por `generate_answer`. Sin eso, el resolver está
      medido en una sola dirección y el `design.md` lo dice.
- [x] 7.4 La conversación de tres turnos que motiva el change, como test de
      integración sobre el grafo real y no como prueba manual
      (`test_three_turns_of_one_conversation`): pregunta que nombra su sujeto,
      seguimiento referencial que se resuelve ANTES de recuperar, y turno que
      fija un anchor que acota la recuperación de ese mismo turno.
- [x] 7.5 `README.md` y `openspec/project.md`: la memoria deja de figurar
      como hueco.

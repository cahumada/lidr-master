# Implementation Tasks

## 1. El wrapper deja de tragarse el motivo de corte

- [x] 1.1 `Completion` en `app/foundation/llm/wrapper.py`: `text: str` y
      `truncated: bool`. `LLM.complete()` pasa a devolverlo.
- [x] 1.2 `OpenAICompatibleChatLLM`: lee `choices[0].finish_reason` y marca
      `truncated` cuando vale `"length"`.
- [x] 1.3 `AnthropicMessagesLLM`: marca `truncated` cuando `stop_reason` vale
      `"max_tokens"`. El chequeo de `"refusal"` que ya existe no cambia.
- [x] 1.4 Los dos loguean el corte con `WARNING` y no con `info`: es pérdida
      de información, no una nota de color.
- [x] 1.5 Actualizar los dobles de LLM en los tests (`FakeLLM`,
      `CapturingLLM`, `RefusingLLM`, `CitingLLM`) al contrato nuevo.

## 2. El cap, medido

- [x] 2.1 `ANSWER_MAX_TOKENS: 1024 → 4096` con comentario bilingüe que cite
      la medición (min 626 / mediana 1373 / máx 3325 sobre 8 preguntas del
      golden set; 6 de 8 se truncaban con 1024) y que aclare que es un CAP y
      no un objetivo.
- [x] 2.2 `.env.example`: el knob, la medición, y que el `max_tokens` de un
      perfil guardado **le gana** a este default.

## 3. El campo viaja hasta la pantalla

- [x] 3.1 `answer_truncated: bool` en `AnswerResponse`.
- [x] 3.2 `AnswerAgentState`, `completed_result`, `paused_result`.
- [x] 3.3 `AnswerAgenticResponse`, `AnswerAgenticProgress` y la pausada.
- [x] 3.4 `lib/ai-service/types.ts`.
- [x] 3.5 Aviso en `answer-console.tsx` que diga qué hacer —subir el tope de
      salida del perfil en `/agents`— y no solo que la respuesta se cortó.

## 4. Tests

- [x] 4.1 `test_wrapper.py`: `finish_reason="length"` marca `truncated`;
      `"stop"` no.
- [x] 4.2 `test_wrapper.py`: `stop_reason="max_tokens"` marca `truncated`;
      `"end_turn"` no; `"refusal"` sigue levantando `LLMError`.
- [x] 4.3 Una completion truncada **se devuelve igual**, con su texto: marcar
      y no rechazar.
- [x] 4.4 `test_answer_router.py` y `test_answer_synthesizer.py`: el campo
      viaja y vale false en el camino normal.

## 5. Cierre

- [x] 5.1 `README.md` de `ai-service`: qué significa el aviso, y que el
      perfil pisa el default.
- [x] 5.2 `uv run python scripts/validate_specs.py`.
- [x] 5.3 `uv run pytest` y `uv run ruff check .` desde `ai-service/` --
      **826 passed, 0 skipped** en 5:31, y ruff limpio.
- [x] 5.4 `npx tsc --noEmit` en `business-backend/`.
- [x] 5.5 Reproducir la pregunta que motivó el change y confirmar que con el
      cap nuevo termina con `end_turn` y escribe `Fuentes citadas`.

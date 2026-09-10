# Implementation Tasks

## 1. Cliente y tipos

- [x] 1.1 Tipos `AnswerAgentic*` en `types.ts` espejando Pydantic.
- [x] 1.2 `postJsonAllowingStatuses` para 200/202 en `base-client.ts`.
- [x] 1.3 Cliente `answer.ts` con `answerAgentic` y `answerAgenticResume`.

## 2. Route Handlers

- [x] 2.1 `POST /api/answer/agentic` relay.
- [x] 2.2 `POST /api/answer/agentic/resume` relay.

## 3. Pantalla

- [x] 3.1 `answer-console.tsx`: formulario, respuesta, traza, gate humano.
- [x] 3.2 Nav + portada + `page.tsx`.

## 4. Verificación

- [x] 4.1 `pnpm lint` y `pnpm build` en verde.
- [x] 4.2 `python scripts/validate_specs.py` en verde.

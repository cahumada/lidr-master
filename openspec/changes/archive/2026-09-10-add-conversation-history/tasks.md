# Implementation Tasks

Depende de `add-conversation-memory` ya en `main`. No mueve el
resolver, el presupuesto ni el prompt `v2`. La pantalla es otro
change (`plan-web`).

## 1. Modelo y persistencia

- [x] 1.1 En `app/generation/conversation/models.py`: `CitationSnapshot`
      (`document_id`, `document_title`, `section`, `bullet_path`,
      `content_hash`) y `HistoryTurn` (pregunta, `resolved_question`,
      `answer` entero, `citations: list[CitationSnapshot]`, `grounded`,
      `created_at`). Ni `text` ni scores del `SearchHit`.
- [x] 1.2 `ConversationSession` gana `title: str | None` e
      `history: list[HistoryTurn]`. `append_history(turn)` appendea
      sin recortar; si `title` es `None` y hay pregunta, la sella
      (whitespace colapsado, tope `CONVERSATION_TITLE_MAX_CHARS`).
      `append_turn()` no se toca.
- [x] 1.3 Test en `tests/generation/conversation/test_models.py`:
      cinco `append_turn` + cinco `append_history` dejan
      `len(turns) == 4` y `len(history) == 5`; el título queda
      pegado a la primera pregunta y no lo pisa la quinta.
- [x] 1.4 Migración alembic (revisa `f3a7c21e9b40`): columnas
      `title VARCHAR` nullable y `history JSONB NOT NULL DEFAULT '[]'`.
      Backfill: `history = turns` donde `history` esté vacío; `title`
      = primera `turns[].question` recortada. Confirmar que
      `alembic/env.py` no excluye `conversation_sessions`.
- [x] 1.5 `ConversationSessionRow` y `_to_domain` leen/escriben
      `title` e `history`. `SessionStore.list_recent(limit, offset)`
      excluye `history` vacío y filas con `updated_at` anterior al
      TTL, ordena por `updated_at` desc. `rename(session_id, title)`
      persiste o devuelve `None` si no existe / venció.
- [x] 1.6 Tests de store en `tests/generation/conversation/test_store.py`
      (se saltan sin `DATABASE_URL`): listado sin vacías ni vencidas,
      orden, `rename`, y que `get` de una fila backfilledeada expone
      `history`.

## 2. Cierre de turno

- [x] 2.1 `close_turn()` en `app/domain/graph/runner.py`
      sigue recortando la respuesta que va a `append_turn`. Además
      arma un `HistoryTurn` con `answer` completo y
      `CitationSnapshot` por cada cita con `document_id`. Un hit sin
      `document_id` no entra al snapshot (no se inventa procedencia).
- [x] 2.2 El camino que pausa en el gate y resume sigue cerrando
      **una** vez: un solo `HistoryTurn` por corrida, el de la
      respuesta aceptada. Reusar el test de integración que ya cubre
      el cierre único de memoria
      (`tests/domain/graph/test_integration.py`) o extenderlo para
      `len(history) == 1`.
- [x] 2.3 `history` no se pasa al sintetizador ni al
      `citation_validator`. Ningún cambio en
      `app/foundation/prompts/answer/v2/` ni en `budget.py`.

## 3. Contrato y router

- [x] 3.1 Setting `CONVERSATION_TITLE_MAX_CHARS = 80` en
      `app/config.py` (comentario bilingüe) y en `.env.example`.
- [x] 3.2 Schemas en `app/api/answer_session.py`: `HistoryTurnView`,
      `SessionSummary` (`session_id`, `title`, `created_at`,
      `updated_at`, `turn_count`), `SessionRename` (`title` con
      `min_length=1` y el tope del setting). `SessionView` suma
      `title`, `history`, `created_at`, `updated_at` sin sacar
      `turns` / `facts` / `anchors` / `max_turns`.
- [x] 3.3 `GET /answer/sessions` — query `limit` (default 50, `le=100`,
      `ge=1`) y `offset` (`ge=0`). 200 + lista. Declarar la ruta
      **antes** de `GET /{session_id}` para que `sessions` no lo
      capture como id.
- [x] 3.4 `PATCH /answer/session/{session_id}` — 200 + `SessionView`;
      404 si falta o venció (mismo `detail` que el GET); 422 si el
      título no pasa el contrato. No hay «des-renombrar» a `null`.
- [x] 3.5 Router delgado: el store lista, renombra y lee; el router
      mapea 404 y arma el `response_model`. Sin SQL en el endpoint.

## 4. Tests de contrato

- [x] 4.1 Extender `tests/api/test_answer_session_router.py` (store
      falso, sin base):
      - GET de una sesión con 5 history / 4 turns devuelve los dos
        slots y el título;
      - GET `/answer/sessions` no incluye vacías ni vencidas y
        respeta `limit`;
      - PATCH 200, 404 y 422 (título vacío / ausente);
      - el snapshot de una cita no incluye `text`.
- [x] 4.2 Happy path + borde del listado vacío (`[]`, no 404).

## 5. Specs y rutas

- [x] 5.1 Delta en
      `openspec/changes/add-conversation-history/specs/conversation-history/spec.md`
      alineado con lo implementado — no con lo deseado.
- [x] 5.2 Filas nuevas en `openspec/standards/app-routes.md`, tabla
      «API del servicio IA»: `GET /answer/sessions` y
      `PATCH /answer/session/{session_id}`. Actualizar la descripción
      de `GET /answer/session/{session_id}` (ahora también history +
      title). Sin filas de BFF: eso es `plan-web`.
- [x] 5.3 Sin cambios de convención ni dependencias nuevas. Un solo
      retoque de inventario en el árbol de
      `ai-service-standards.md` (`conversation/` ahora nombra
      `history`).
- [x] 5.4 `ai-service/README.md` y `openspec/project.md` nombran el
      slot `history` y los endpoints de lista/rename. Sin capability
      nueva en `openspec/specs/` — eso es al archivar.

## 6. Verificación

- [x] 6.1 `uv run pytest` y `uv run ruff check .` en verde desde
      `ai-service/`. 842 passed, ruff limpio.
- [x] 6.2 `python scripts/validate_specs.py` desde la raíz, sin
      errores.

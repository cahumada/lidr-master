# Implementation Tasks

## 1. Los filtros del request llegan al estado
- [x] 1.1 `initial_state()` en `app/domain/graph/runner.py` siembra
  `state["request_filters"]` con `module_code` y `window_type_name` del body.
  Ausentes o vacíos NO se siembran: `None` significa "el cliente no pidió
  recorte", que no es lo mismo que una lista vacía.
- [x] 1.2 No sembrar `state["filters"]` desde acá. El planner es el único autor
  de la clave que el retriever lee — ver `design.md` §3.

## 2. La precedencia, en un solo lugar
- [x] 2.1 En `app/domain/graph/agents/query_planner.py`, resolver las tres
  fuentes en el orden `request → pregunta → anchor`, por campo y no por bloque:
  un request que trae `module_code` pero no `window_type_name` no debe borrar el
  tipo de ventana que la pregunta o un anchor aportaron.
- [x] 2.2 Registrar el origen de cada valor efectivo (`request` / `question` /
  `anchor`) junto a los filtros resueltos.
- [x] 2.3 Extender el comentario de `_apply_anchors` para que la regla completa
  quede en el código, no solo en este change: hoy documenta dos fuentes y ahora
  hay tres.
- [x] 2.4 La contribución del planner en `agent_contributions` nombra la fuente
  de cada filtro, no solo el valor.

## 3. Reportar lo que se aplicó
- [x] 3.1 Los filtros efectivos y su origen en la respuesta agéntica
  (`app/generation/rag/schemas.py`).
- [x] 3.2 Que viajen en los tres payloads: completado, pausado y progreso
  (`app/api/answer_agentic.py`). Un turno pausado ya aplicó el filtro, así que
  ocultárselo a quien revisa sería esconder justo lo que necesita para decidir.

## 4. Tests
- [x] 4.1 **El test que el bug pide, y no es el obvio:** un `module_code` que no
  matchea nada produce **cero** hits. Un test que solo verifique "los resultados
  son del módulo pedido" pasa con el bug presente — ver `design.md` §4.
- [x] 4.2 Precedencia: request gana sobre un código en la pregunta; la pregunta
  gana sobre un anchor; y un request parcial no borra lo que aportaron las otras
  fuentes.
- [x] 4.3 Sin filtros en el request, el estado y los hits son **idénticos** a los
  de antes de este change: es la regresión que importa, porque el camino sin
  filtros es el que usan todos los evals.
- [x] 4.4 Paridad entre endpoints: la misma pregunta con el mismo filtro por
  `POST /answer` y por `POST /answer/agentic` recorta al mismo **módulo**.
      > Corregido al verificar: el enunciado original decía «al mismo conjunto de
      > documentos» y eso es falso por diseño — el camino agéntico descompone la
      > pregunta e intercala los hits de cada subconsulta, así que los documentos
      > difieren aunque el recorte sea el mismo. Verificado el 2026-09-10 con
      > `module_code=['DMECAR']`: los dos endpoints devuelven 6 citas y todas de
      > `DMECAR`.
- [x] 4.5 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
      > 884 passed, ruff limpio. Dos corridas intermedias fallaron un test cada
      > una (`test_purge_removes_only_what_expired`,
      > `test_summarize_filters_session_and_purpose`) por correr **dos suites a
      > la vez contra la misma base compartida**: los dos tests afirman conteos
      > exactos sobre Postgres real. Aislados y en serie pasan. No es de este
      > change.

## 5. Specs
- [x] 5.1 Delta en `specs/answer-orchestration/spec.md`.
- [x] 5.2 `python scripts/validate_specs.py` sin errores desde la raíz.
- [x] 5.3 Sin cambios de estándar ni de `app-routes.md`: no hay ruta nueva.

## 6. Verificar
- [x] 6.1 Contra el servicio local, la reproducción original: `module_code` con
  un valor inexistente y una pregunta cualquiera, por el endpoint agéntico, debe
  dar cero citas. Antes de este change daba cinco.
- [x] 6.2 Anotar en el proposal el antes/después de esa reproducción.
- [x] 6.3 Declarar si los selectores de la consola quedaron funcionando sin
  tocar `business-backend/`. Mostrar los filtros efectivos en la pantalla es un
  change de `web` aparte.

# Implementation Tasks

## 1. OpenSpec

- [x] 1.1 `proposal.md` con el problema observado y lo descartado con su
      razón.
- [x] 1.2 `design.md` con qué se afirma, qué es ilustrativo, y por qué
      el diagrama se deriva en vez de dibujarse.
- [x] 1.3 Deltas de `agent-profiles` y `web-console`.

## 2. Catálogo del servicio

- [x] 2.1 `EXAMPLE_QUESTION` con su id del golden curado y los
      documentos anotados, en `catalog.py`.
- [x] 2.2 `AgentSpec` lleva `example_input` y `example_output`; los seis
      specs los declaran.
- [x] 2.3 `graph_flow()` sirve `example` y los dos campos por nodo.
- [x] 2.4 `GET /config`: `FlowNodeView` con los campos nuevos,
      `FlowExampleView`, `GraphFlowView.example`.

## 3. Tests del servicio

- [x] 3.1 Todo spec tiene ejemplo de entrada y de salida.
- [x] 3.2 Drift: las subconsultas del ejemplo del planificador salen de
      `decompose(EXAMPLE_QUESTION)` y los filtros de
      `_suggest_filters(EXAMPLE_QUESTION)`.
- [x] 3.3 La pregunta del ejemplo es la del id anotado en
      `evals/golden_curated.json`.
- [x] 3.4 `GET /config` sirve el ejemplo y sus campos por nodo.

## 4. Consola

- [x] 4.1 Tipos del ejemplo en `lib/ai-service/types.ts`.
- [x] 4.2 Diagrama de hub derivado de `flow.edges`, con caída a lista
      plana.
- [x] 4.3 Nodos en orden de ejecución (orquestador → `ladder` → gate),
      numerados, con entra → sale.
- [x] 4.4 Pregunta de ejemplo arriba con su procedencia; lo ilustrativo
      marcado.

## 5. Verificación

- [x] 5.1 `uv run pytest` y `uv run ruff check .` desde `ai-service/`.
- [x] 5.2 `pnpm lint` y `pnpm build` desde `business-backend/`.
- [x] 5.3 `python scripts/validate_specs.py` desde la raíz.
- [x] 5.4 Smoke en el navegador: `/agents/flow` renderiza el recorrido
      con los datos del servicio.

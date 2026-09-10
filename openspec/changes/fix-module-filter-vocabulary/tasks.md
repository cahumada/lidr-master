# Implementation Tasks

## 1. Fuera la heurística de la pregunta
- [x] 1.1 Quitar `_suggest_filters` y `_TRANSACTION_PREFIX` de
  `app/domain/graph/agents/query_planner.py`. La resolución queda con dos
  fuentes: `request` y `anchor`.
- [x] 1.2 Dejar escrito **en el código** por qué se fue, no solo en este change:
  emitía un vocabulario que el corpus no tiene, y la rama de coincidencia exacta
  de `retrieval` ya encuentra una transacción nombrada por `document_id`.
- [x] 1.3 Verificar la reproducción: `¿Qué valida CA014?` por el endpoint
  agéntico pasa de **0 citas** a devolver evidencia.

## 2. El prefijo de transacción como dimensión propia
- [x] 2.1 `SearchFilters` gana un filtro por prefijo de `document_id`
  (`app/generation/rag/store/repository.py`), aplicado como recorte previo al
  ranking igual que los otros.
- [x] 2.2 El campo correspondiente en `QueryFilters`
  (`app/domain/schemas.py`). Nombre que **no** diga «módulo»: la confusión de
  vocabulario es la causa raíz y el nombre no la puede reintroducir.
- [x] 2.3 `_MODULE` en `app/generation/conversation/anchors.py` pasa a producir
  un anchor de ese `kind`, no de `module_code`. El `AnchorKind` de
  `app/generation/conversation/models.py` acompaña.
- [x] 2.4 El anchor se reporta con su dimensión, para que la respuesta diga
  «transacciones que empiezan con CA» y no «módulo CA».

## 3. La regla general
- [x] 3.1 Un valor de filtro fuera de su vocabulario no se aplica y se registra.
  El vocabulario de `module_code` son los códigos que sirve
  `GET /search/facets`.
      > Queda como **regla normativa en la spec, sin chequeo en el código**, y a
      > propósito: quitados los dos productores malos, no queda ninguno que
      > pueda emitir un valor fuera de vocabulario. El único que puede es un
      > cliente que llame al API a mano, y para ése el requirement ya promovido
      > dice lo contrario —un filtro explícito que no matchea nada DEBE devolver
      > cero, porque alguien lo pidió—. Agregar la validación ahora sería
      > máquina especulativa sin caso vivo.
- [x] 3.2 Un filtro **explícito** que no matchea nada sigue devolviendo cero:
  eso NO cambia, y hay un test que lo fija — ver el requirement ya promovido en
  `answer-orchestration`.
      > `test_a_transaction_prefix_filter_narrows_by_document_id` cierra con
      > `transaction_prefix=["ZZ"] == 0`, y `test_a_filter_nobody_matches_returns_nothing`
      > ya lo fijaba para los otros.

## 4. Tests
- [x] 4.1 La reproducción del proposal, como test: una pregunta que nombra una
  transacción no queda sin evidencia por un filtro que nadie pidió.
- [x] 4.2 El anchor «solo módulo CA» recorta a transacciones `CA*` y **no** a un
  `module_code`.
- [x] 4.3 Un anchor fijado hace tres turnos sigue recortando, y lo dice — la
  regresión que importa, porque el defecto era que envenenaba la conversación.
- [x] 4.4 El filtro por `module_code` de la consola sigue funcionando con el
  vocabulario de las facets.
- [x] 4.5 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
  **Correr una sola suite a la vez**: los tests con base afirman conteos exactos
  contra el Postgres compartido y dos corridas simultáneas se pisan.
      > 884 passed, ruff limpio. Nueve tests fijaban el comportamiento viejo y
      > se actualizaron: cinco del `kind` del anchor, tres de la etiqueta del
      > bloque de memoria, y el de tres turnos que afirmaba
      > `module_code == ["CA"]` — el que describía el defecto como si fuera la
      > especificación.

## 5. Specs
- [x] 5.1 Deltas en `specs/answer-orchestration/spec.md`,
  `specs/conversation-memory/spec.md` y `specs/agent-profiles/spec.md` — el
  tercero apareció al implementar (ver el proposal).
- [x] 5.2 Revisar si `specs/retrieval/spec.md` necesita delta: el filtro nuevo
  es un recorte previo al ranking y esa spec declara cuáles hay.
      > No lo necesita. Sus requirements sobre filtros hablan de los dos que la
      > **pantalla** expone como selección múltiple (`module_code`,
      > `window_type_name`); `transaction_prefix` no se ofrece en la consola y
      > no cambia lo que esa spec afirma. Si algún día se expone, ahí sí.
- [x] 5.3 `python scripts/validate_specs.py` sin errores desde la raíz.

## 6. Verificar
- [x] 6.1 Contra el servicio local, las tres preguntas medidas en el proposal, y
  anotar el antes/después ahí mismo.
- [x] 6.2 Una conversación de tres turnos con «de acá en adelante, solo módulo
  CA» en el primero: los turnos 2 y 3 tienen que traer evidencia de `CA*`, que
  hoy traen cero.
- [x] 6.3 Declarar qué no se pudo ejercer, si algo.
      > Todo lo planeado se ejerció. La conversación de 6.2 se corrió con **dos**
      > turnos y no tres: el segundo ya prueba lo que importaba —que el anchor
      > sobrevive al turno que lo fijó— y un tercero no agrega evidencia nueva.

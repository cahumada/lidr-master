## Why

`/agents/flow` ya muestra los seis nodos del grafo con su rol, su
explicación y sus tools, todo derivado de `GET /config`. Pero se lee como
un glosario: el dueño del repo abrió la pantalla y no le quedó clara **la
función de cada nodo**. El texto está bien y aun así no alcanza, y se
entiende por qué:

- Cada ficha describe el nodo **en abstracto** («parte preguntas
  compuestas y sugiere filtros»). No hay un dato concreto que lo haga
  aterrizar: qué entra, qué sale.
- El «diagrama» son once líneas `origen → destino` en una lista plana.
  El grafo real es un hub —orquestador en el centro, cuatro
  especialistas que vuelven a él, un gate que termina— y la lista plana
  esconde exactamente esa forma, que es lo que explica por qué el
  orquestador aparece seis veces en una corrida.
- El orden en que se listan los nodos es el del catálogo, no el de la
  ejecución, así que la pantalla no cuenta ninguna secuencia.

La consola tiene una pregunta real del negocio a mano —`evals/
golden_curated.json` son preguntas que un usuario hizo, anotadas por
alguien que conoce el seguro— y no la usa en ninguna pantalla
explicativa.

## What Changes

- `ai-service`: el catálogo declara **un ejemplo trabajado**: una
  pregunta real del golden curado (`U-multi-lote-pac-rechazos`) y, por
  nodo, qué recibe y qué deja en el estado cuando esa pregunta pasa por
  él. Vive al lado del catálogo, por la misma razón que el catálogo vive
  al lado del grafo.
- `ai-service`: `GET /config` sirve el ejemplo dentro de `flow`
  (`flow.example` + `example_input` / `example_output` por nodo).
- `ai-service`: test de drift sobre la parte determinista del ejemplo —
  las subconsultas del ejemplo del planificador SHALL salir de
  `decompose()` corrido sobre la pregunta del ejemplo, y los filtros de
  `_suggest_filters()`. Un ejemplo que el código ya no produce falla en
  CI en vez de quedar como prosa vieja.
- `business-backend`: `/agents/flow` se reordena en **recorrido**: la
  pregunta de ejemplo arriba, los nodos en orden de ejecución
  (orquestador, escalera, gate) numerados, y en cada ficha el par
  entra → sale del ejemplo.
- `business-backend`: el diagrama pasa de lista de aristas a **hub**
  (START → orquestador ⇄ especialistas → gate → END), **derivado** de
  `flow.edges`. Si las aristas no tienen forma de hub, cae a la lista
  plana actual: la pantalla no dibuja una topología que el servicio no
  declaró.

### Deliberadamente descartado (con razón)

- **Grabar una corrida real como fixture.** Sería el ejemplo más
  honesto y es el que no se puede sostener: necesita corpus cargado y
  un modelo en CI, y el corpus del cliente no viaja al repo público.
  Un fixture que nadie puede regenerar envejece en silencio, que es el
  problema que este change viene a resolver.
- **Escribir los ejemplos en TypeScript.** Es exactamente la divergencia
  que el catálogo en el servicio existe para impedir.
- **Ejemplo de salida del sintetizador afirmado como real.** Es el único
  nodo LLM-driven: su salida cambia con el modelo y con la persona. El
  ejemplo se marca como ilustrativo en la pantalla en vez de fingir que
  es una respuesta grabada.
- **Varias preguntas de ejemplo con selector.** Un selector que no
  cambia nada más que el texto de las fichas es una pantalla más grande
  explicando lo mismo. Una pregunta, compuesta, que ejercita los seis
  nodos.
- **Editor / tooltip de aristas.** El flujo se mira, no se reescribe —
  igual que en `add-named-agent-profiles-and-flow`.

## Capabilities

### New Capabilities

(ninguna — extiende capabilities existentes)

### Modified Capabilities

- `agent-profiles`: el catálogo, además de la topología, sirve un
  ejemplo trabajado por nodo.
- `web-console`: la pantalla de flujo se lee como recorrido de una
  pregunta real, con diagrama de hub derivado de las aristas.

## Impact

- `ai-service/app/domain/graph/catalog.py` — `EXAMPLE_QUESTION`,
  `example_input` / `example_output` por spec, `flow.example`
- `ai-service/app/api/config.py` — `FlowNodeView`, `FlowExampleView`,
  `GraphFlowView`
- `ai-service/tests/domain/graph/test_catalog.py` — drift del ejemplo
  determinista contra `decompose()` y `_suggest_filters()`
- `ai-service/tests/api/test_config_router.py` — el ejemplo viaja en
  `GET /config`
- `business-backend/lib/ai-service/types.ts` — campos del ejemplo
- `business-backend/app/agents/flow/flow-console.tsx` — recorrido,
  diagrama de hub, fichas con entra → sale
- `business-backend/app/agents/flow/page.tsx` — intro
- `openspec/changes/add-flow-worked-example/specs/`

## Enfoque

Master–detalle en la misma `PageFrame` (`max-w-6xl`): lista de agentes
a la izquierda, workspace a la derecha. En viewport chico la lista
pasa a una fila de chips con scroll horizontal. No se agrega un
componente Tabs de shadcn: un `role="tablist"` de botones alcanza y
el vecino de la consola no usa Tabs.

El workspace del sintetizador tiene un segundo picker de perfiles.
Un campo vacío sigue significando «default del servicio». El prompt
compuesto, el system prompt y los guardrails de sistema viven en
`<details>` cerrados: la spec pide que se *vean*, no que estén
abiertos al entrar.

## Alternativas descartadas

- **Accordion de todos los agentes.** Sigue siendo un scroll. El
  problema era la cantidad de bloques abiertos, no la falta de un
  chevron.
- **Tabs de shadcn.** Habría que copiar un componente que ninguna
  otra pantalla usa. Los botones del tema ya expresan selección
  (`aria-expanded` / `aria-selected`).
- **Página por agente (`/agents/[key]`).** Rompe el inventario de
  [app-routes.md](../../standards/app-routes.md) y el “catálogo en
  una pantalla” que ya documentan los changes de perfiles. El picker
  en cliente no inventa rutas.

## Por qué el sintetizador es la selección inicial

Es el único `configurable` del catálogo. Quien abre Configuración →
Agentes viene a editar persona, guardrails o modelo. Los
deterministas siguen a un clic, sin formulario.

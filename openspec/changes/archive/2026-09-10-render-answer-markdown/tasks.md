# Implementation Tasks

## 1. Dependencias

- [x] 1.1 `pnpm add react-markdown remark-gfm` en `business-backend/`.
- [x] 1.2 Confirmar que NO entra `rehype-raw`: sin HTML crudo, que es lo que
      mantiene el markup fuera del alcance de lo que escriba el modelo.

## 2. El componente

- [x] 2.1 `app/answer/answer-markdown.tsx`: mapa de componentes explícito
      para `p`, `strong`, `em`, `ul`/`ol`/`li`, `h1`-`h4`, `code`, `pre`,
      `a`, `blockquote`, `hr` y `table`.
- [x] 2.2 Estilos con los tokens de shadcn que la consola ya usa —
      `text-muted-foreground`, `border`, `bg-muted` — para que la respuesta
      no parezca de otra aplicación.
- [x] 2.3 Links con `rel="noopener noreferrer"` y `target="_blank"`.
- [x] 2.4 `pre` y `table` con `overflow-x-auto` en su propio contenedor: una
      tabla ancha no puede ensanchar la burbuja ni la página.
- [x] 2.5 Los encabezados del markdown se renderizan en una escala CONTENIDA
      (un `h1` del modelo no puede verse más grande que el título de la
      pantalla). El modelo no conoce la jerarquía visual de la consola.

## 3. Integración

- [x] 3.1 `answer-console.tsx` usa `AnswerMarkdown` para `result.answer`.
- [x] 3.2 Y también para la respuesta parcial de un turno pausado en el gate,
      que hoy comparte el mismo `whitespace-pre-wrap`.
- [x] 3.3 La pregunta del usuario queda como texto plano: la escribió una
      persona y `**` ahí es literal.
- [x] 3.4 Los avisos del sistema (contexto recortado, pregunta resuelta) no
      pasan por el renderer: no son contenido del modelo.

## 4. Verificación

- [x] 4.1 `npx tsc --noEmit` y `pnpm lint` sin errores.
- [x] 4.2 Verificado con una cadena conocida contra el componente montado en
      el dev server, y NO esperando a que el modelo escribiera una: 1
      `<strong>`, 2 `<ul>`, 1 `<ol>`, 7 `<li>`, 1 `<table>` en su contenedor
      con scroll, 1 `<code>`, y **0 asteriscos literales**. Un modelo que
      elige no usar negritas no prueba nada sobre el renderer.
- [x] 4.5 Recorrer una respuesta real en claro Y en oscuro. Lo verificado
      arriba fue en oscuro; el modo claro queda sin mirar.
      > Verificado por el dueño del repo el 2026-09-10. El agente no pudo ejercerlo: la consola exige login y no puede autenticarse.
- [x] 4.3 Comprobar con una respuesta que traiga una tabla que el ancho
      scrollea y no rompe el layout.
- [x] 4.4 Comprobar que un `<script>` escrito en el texto se muestra como
      texto y no se ejecuta.

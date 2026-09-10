## Sidebar, no otra fila de links

El tema Woken ya trae tokens `--sidebar-*` en claro y oscuro. Un sidebar
shadcn los usa de primera; un nav horizontal no. Agrupar por módulo en un
sidebar es el patrón que el propio registro de shadcn resuelve (collapsible,
sheet en móvil, estado activo). Reinventar eso con `<nav>` y `flex` sería
el mismo trabajo con peor accesibilidad.

La alternativa —tabs en cada módulo, nav de top igual— deja la
configuración y el RAG un click más lejos y no aprovecha los tokens que
ya pagamos al pegar el tema.

## Chat de sesión, no memoria del servicio

`POST /answer/agentic` es una corrida: una pregunta, un `thread_id`, un
resultado o una pausa. Inventar un hilo persistente en el servidor sería
otro change (checkpointer, resume entre preguntas, contexto acumulado).
Acá el chat es **presentación**: cada envío appendea un turno en el estado
del browser. Cerrar la pestaña lo pierde. Eso es honesto —la spec no
puede afirmar memoria que el código no tiene— y alcanza para que se sienta
un chat y no un formulario que se borra.

## Opciones del retrieval fuera del compositor

El formulario actual pone filtros y tres toggles medidos arriba de la
pregunta. En un chat eso empuja el compositor lejos. Van a un panel
colapsable (sheet en móvil, aside en desktop) para que el hilo ocupe el
centro, sin esconder los knobs: siguen siendo los mismos, con las mismas
mediciones.

## Solo los componentes shadcn que se usan

`sidebar` arrastra `separator`, `tooltip` y `sheet`. El chat usa
`scroll-area`. Nada más. Un `components/ui/` de cuarenta archivos sigue
siendo la versión shadcn de pre-construir capas vacías.

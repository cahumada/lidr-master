# Diseño — historial en la consola, no en el nav

El contrato ya está en `add-conversation-history`. Acá se decide
cómo se ve y qué se deja de hacer.

---

## 1. «Chat nuevo» ya no es `DELETE`

`add-conversation-memory` fijó: empezar de nuevo descarta la
sesión. Tenía sentido cuando la fila *era* la memoria de un hilo
que el usuario dio por muerto. Con historial, esa fila es el
transcript. Borrarla al abrir otro chat es el defecto que este
change viene a sacar.

| Acción | Qué hace |
|---|---|
| Chat nuevo | Limpia el hilo local, saca `?session=`, no llama `DELETE`. El próximo envío crea otra sesión (sigue siendo perezoso). |
| Borrar en la lista | `DELETE /api/answer/session/{id}`. Si era el activo, vuelve al compositor vacío. |

El scenario «hilo nuevo» de `web-console` se modifica. El `DELETE`
no desaparece: cambia de disparador.

## 2. La lista vive adentro de `/answer`

No es un ítem de `CONSOLE_MODULES`. El sidebar de la app es nav de
módulos; mezclar ahí «CA014 alta» con «Corpus» confunde dos
escalas. El patrón de ChatGPT —columna de hilos junto al
compositor— cabe en el inset que el chat ya ocupa entero
(`PageFrame` no aplica).

En viewport chico, la misma lista va a un `Sheet`. `use-mobile`
ya existe; no se inventa otro drawer.

## 3. La URL es el puntero, no `localStorage`

Tres formas de sobrevivir un F5:

| Alternativa | Por qué pierde / gana |
|---|---|
| Solo estado React | Es el defecto de hoy. |
| `localStorage` del último `session_id` | Dos pestañas se pisan; un operador en otra máquina no ve el hilo; y el dato ya está en el servicio. |
| `/answer?session=<id>` | El Server Component puede pasar el id; el cliente hace el GET. Un F5 restaura. Compartir el link abre el mismo transcript. No hay segunda fuente de verdad. |

`page.tsx` lee `searchParams.session` y se lo pasa al console.
Elegir una fila hace `router.replace` con el query (sin perder el
hilo de React si se puede; si el replace remonta, el GET
rehidrata). Un id desconocido o vencido (404) se trata como
lista + compositor vacío, con el error del BFF — no error page.

No se prefetcha el transcript en el Server Component: eso
importaría `lib/ai-service` en el camino de la página (ya lo
hace para facets) y un 404 del servicio tumbaría el primer
pintado. El cliente pide el GET; si falla, alerta y lista.

## 4. Un snapshot no es un `SearchHit`

`CitationList` hoy pinta `hit.text` en un `<pre>`. El historial
trae `document_id`, `document_title`, `section`, `bullet_path`,
`content_hash`. Inventar `text: ""` y mostrar un recuadro vacío
es peor que no mostrar el chunk.

La lista de citas acepta las dos formas. Con `text`, el recuadro
de siempre. Sin `text`, badge + título + sección. El
`content_hash` es la key. No se rehidrata el chunk desde
`/search`: sería otra ronda de retrieve y no el registro de lo
citado.

Los turnos reabiertos no tienen `routing_history` ni el panel
«Flujo en vivo». Eso es diagnóstico de una corrida, no del hilo
(`add-conversation-history` `design.md` §3). Un turno
reabierto se muestra como cerrado: pregunta, markdown, citas,
`grounded`. Si estaba pausado en el gate y nunca cerró, no está
en `history` — el compositor vacío + la lista no mienten.

## 5. La lista es del tenant

El servicio no autentica. El BFF no agrega `user_id` ni filtra
por la sesión de Auth.js: eso sería un índice paralelo que el
cierre de turno no actualiza, y un 500 a mitad de camino dejaría
hilos huérfanos. Todos los operadores ven los mismos resúmenes.
Queda escrito en la spec y en un texto corto sobre la lista
(«Conversaciones de este entorno»), no como «tus chats».

## 6. `patchJson`, no reciclar `putJson`

El servicio expone `PATCH`. Mandar PUT porque el cliente base no
tiene el verbo es inventar un contrato. Se agrega `patchJson` al
lado de `putJson`, mismo shape. No hay paquete nuevo.

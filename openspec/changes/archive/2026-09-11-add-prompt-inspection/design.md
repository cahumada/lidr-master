# Diseño

## 1. Se guarda al enviar, y no se reconstruye después

Reconstruir el prompt a pedido sería más barato —cero almacenamiento— y sería
**incorrecto**. Lo que entra al prompt depende de cosas que cambian entre la
respuesta y el momento de mirarla:

| pieza | quién la mueve |
|---|---|
| persona y guardrails | `/agents`, en cualquier momento |
| perfil del sintetizador | se elige por corrida |
| memoria de la sesión | crece con cada turno |
| corrida activa del mirror | `/business-db` |
| recortes de presupuesto | dependen de todo lo anterior |

Un re-render mostraría un prompt que nunca se envió, presentado como si sí. Es
el mismo defecto que `business-db-context` evita al fechar la vigencia con el
`created_at_utc` de la corrida en vez de `now()`: una respuesta que depende del
reloj de pared pasa hoy y falla la semana que viene sin que nadie haya tocado
nada.

Y es peor acá que allá, porque el caso de uso es justamente diagnosticar una
respuesta mala: la única versión que sirve es la que la produjo.

## 2. `prompt_id` en el payload, no el prompt

`ANSWER_MAX_CONTEXT_TOKENS` es 16.384, así que un prompt ronda los **60 KB** con
el contenido del corpus adentro. Devolverlo en cada respuesta:

- se lo manda por la red a **todos**, incluido el `usuario` que no puede verlo —
  una autorización que se aplica recién en el cliente no es una autorización;
- multiplica por varias veces el tamaño de cada payload de turno, para un dato
  que casi nunca se mira.

El payload lleva un `prompt_id` y la consola pide el texto recién cuando se abre
el modal.

## 3. La retención se barre en la escritura, no con un cron

7 días. El barrido va **en el mismo `INSERT`**: cada escritura borra las filas
del tenant que pasaron la ventana.

Un cron sería más prolijo y tiene un modo de fallo concreto: nadie lo configura
en Railway, y la tabla crece sin que nada lo diga hasta que la base se llena. Una
política de retención que depende de un paso manual es una política que no
existe. El barrido en la escritura no se puede olvidar, está acotado por el
índice de `(tenant_id, created_at)`, y es proporcional a lo que se escribe.

El costo es un `DELETE` por respuesta. Es aceptable: la síntesis ya pagó una
llamada al LLM de 40–50 segundos.

## 4. Por qué una tabla propia y no `llm_usage_events`

`llm_usage_events` ya tiene una fila por completion, con su `thread_id` y su
`session_id`. Tentador, y no: esa tabla es **contabilidad**, se conserva para
agregados históricos y la lee `/usage`. Colgarle 60 KB de texto por fila le
cambiaría el perfil de crecimiento a un dato que hoy es chico y permanente, y le
metería una política de retención de 7 días a una tabla que no la quiere.

Dos tablas con dos ciclos de vida distintos, unidas por `thread_id` cuando haga
falta cruzarlas.

## 5. El gate de rol baja al route handler

La consola chequea el rol en `app/(console)/(admin)/layout.tsx`, y la pertenencia
a ese grupo es el **file system**: una pantalla está protegida porque está en ese
directorio. Es una buena decisión para pantallas y no alcanza acá por dos
motivos:

1. `app/api/` no está bajo `(admin)/`, así que **ningún route handler mira el
   rol hoy**. Se puede comprobar: `/api/usage/summary` responde a cualquier
   sesión, aunque `/usage` sea solo de administración.
2. `/answer` **no es** una pantalla de administración. El link va a vivir en una
   pantalla que cualquiera abre, así que el rechazo tiene que estar en el
   servidor y no en si se pinta el botón.

Este change trae `lib/auth/api-guards.ts` con un `requireAdmin()` que resuelve la
sesión con `auth()` —el secreto, cerca de los datos, igual que el layout— y
devuelve 403 antes de tocar el servicio.

**El servicio no distingue personas.** Lo autentica un token compartido y un
token no es una persona: los roles viven en la sesión de la consola. El endpoint
del servicio queda tan protegido como todo el resto del servicio, ni más ni
menos, y eso ya está escrito en `web-console`.

## 6. Un turno reabierto no inventa el link

`web-console` ya dice que un turno cargado desde `history` no muestra cifras de
tokens salvo que el snapshot las traiga, para que la consola no escriba ceros que
se lean como una medición. El mismo criterio: sin `prompt_id` en el snapshot, no
hay link. Mostrar uno que lleva a un 404 —o peor, a un prompt de otro turno— es
la versión de ese defecto en esta pantalla.

# Diseño — historial de conversación, no más memoria

`add-conversation-memory` resolvió la recuperación de un seguimiento
(«¿y para siniestros?»). Este change resuelve otra cosa: que el
operador pueda **ver de nuevo** lo que ya preguntó. Mezclarlas es el
error que el change anterior evitó a propósito — y el que hay que
seguir evitando.

---

## 1. El transcript no entra al prompt

La ventana de 4 pares existe para que el sintetizador no se repita, y
se recorta **antes** que cualquier chunk. Si el transcript de 20
turnos con respuestas enteras y citas pasara a ser `turns`, el
presupuesto de memoria (`CONVERSATION_MEMORY_MAX_TOKENS = 1024`)
dejaría de significar lo que significa, y la evidencia perdería el
desempate que `add-answer-context-budget` le ganó.

Por eso hay un cuarto slot, no un `max_turns` más alto:

| Slot | Quién lo lee | Cuándo se pierde |
|---|---|---|
| `facts` | resolver + system prompt | nunca (hasta el TTL) |
| `anchors` | retriever (filtro default) + consola | cuando el usuario lo quita |
| `turns` | sintetizador (`answer/v2`) | al pasar de 4 pares, o cuando el presupuesto recorta |
| `history` | `GET` / la consola | solo al TTL o al `DELETE` |

`append_turn()` y `append_history()` son dos métodos. El runner llama
a los dos al cerrar. Un test fije que cinco turnos dejan `len(turns)
== 4` y `len(history) == 5`. Si un día alguien «unifica» los slots
para ahorrarse una columna, ese test es el que tiene que romper.

## 2. Por qué otra columna JSONB y no dejar de recortar `turns`

Tres alternativas, y por qué pierden:

| Alternativa | Por qué pierde |
|---|---|
| Dejar de recortar `turns` y recortar solo al armar el prompt | El GET actual *es* la ventana. Quien lo consume hoy (la consola no, pero un cliente que lea memoria) pasaría a recibir el transcript. Y la respuesta seguiría cortada a 600 caracteres, sin citas: el reload seguiría mudo en procedencia. |
| Tabla `conversation_turns` (una fila por turno) | Se consulta el hilo entero, nunca «los turnos 12–15 de la sesión X». Una fila JSONB por conversación es el mismo call que ya justificó `facts`/`anchors`/`turns`. Normalizar ahora es una migración más un join para un único lector. |
| Guardar el historial en Prisma, en la consola | Parte la fuente de verdad: el servicio cierra el turno y la consola tendría que persistir una copia. Un 500 del BFF después de un 200 del grafo perdería el turno en silencio. El servicio ya tiene la fila y el momento exacto del cierre. |

La columna nueva se llama `history` y no se pisa `turns`. El backfill
copia lo que hay (`turns` → `history`) porque es lo único recuperable;
no se inventan citas ni se «des-recortan» respuestas.

## 3. Qué guarda un `HistoryTurn`

La consola de hoy pinta, por turno, más que pregunta y respuesta:
citas, `grounded`, pregunta resuelta. Recargar y devolver prosa suelta
sería mostrar una respuesta de seguros **sin procedencia**, que es
exactamente la pérdida de negocio que las reglas del repo prohíben
tragarse.

Tampoco se serializa el `SearchHit` entero. `text` es el chunk
recuperado (cientos de tokens por hit, por turno); `score` / `branches`
/ `ranks` son del pipeline de *ese* retrieve, no del registro de «qué
documento se citó». El snapshot es lo que un operador necesita para
verificar la respuesta al reabrirla:

```
document_id, document_title, section, bullet_path, content_hash
```

`content_hash` es la identidad de la fila en `chunks`. Si más adelante
hace falta rehidratar el texto, se busca por hash; no se duplica el
corpus adentro de cada conversación.

`grounded` viaja. `confidence`, `routing_history`, `activity` y el
estado de pausa del gate **no**: son diagnóstico de una corrida, no
del hilo. Un turno que todavía está en `awaiting_human_review` no
existe en `history` — se escribe cuando `close_turn()` corre, una
vez, al cerrar, igual que la memoria.

La respuesta en `history` es la prosa completa, no
`answer[:TURN_ANSWER_MAX_CHARS]`. Ese tope existe para no gastar
presupuesto de evidencia en que el modelo se relea; el transcript no
compite por ese presupuesto.

## 4. La lista es del tenant, no de un usuario

`add-console-authentication` lo dejó escrito: atar
`conversation_sessions` a un usuario «necesita que el servicio sepa
quién pregunta». El servicio no lo sabe. Tres formas de fingirlo, y
por qué no:

| Alternativa | Por qué pierde |
|---|---|
| `user_id` en el body/header, sin autenticar el servicio | Cualquiera que alcance la URL de Railway lista o lee las conversaciones de quien quiera. Peor que hoy: hoy un UUID v4 no se enumera. |
| Lista solo en Prisma, filtrada por la sesión de Auth.js | El BFF se vuelve dueño del índice y el servicio dueño del cuerpo. Dos writes, un solo cierre. El 500 a mitad de camino es un turno huérfano. |
| No listar: la consola recuerda ids | Resuelve el F5 si el browser guarda el id. No resuelve «qué pregunté la semana pasada» en otra máquina, ni un operador que limpia el storage. El servicio ya tiene las filas. |

**Decisión:** `GET /answer/sessions` lista las conversaciones no
vacías y no vencidas del despliegue. Hoy hay un tenant por entorno.
Quien alcanza Railway ya puede preguntarle al corpus; lo que este
endpoint agrega es **enumerar** los hilos de los operadores.

Eso es un riesgo nuevo y se trata como tal: queda en la spec, en este
diseño y en el contrato (el path se llama como se llama, sin un
`/mine` mentiroso). El change que lo cierra es autenticar
`ai-service` y *entonces* colgar `owner_id` de un token que el
servicio verifica — el mismo orden que `add-console-authentication`
ya fijó para el tenant. No se invierte acá.

## 5. Título barato, renombrable

Un sidebar necesita una línea por fila. Generarla con el LLM sería
una llamada por conversación para resumir una pregunta que el usuario
acaba de escribir. El título default es esa pregunta, normalizada
(whitespace colapsado) y cortada a `CONVERSATION_TITLE_MAX_CHARS`.
Se sella en el primer `append_history()` y no se pisa con las
siguientes — un seguimiento referencial («¿y para siniestros?») es
peor etiqueta que la pregunta que nombró el sujeto.

`PATCH /answer/session/{id}` con `{ "title": "…" }` lo cambia. Tope
el mismo; vacío o solo espacios → 422. No hay `DELETE` del título:
volver al default es mandar la primera pregunta otra vez, o dejarlo.

## 6. Paginación, no un dump

El índice por `updated_at` ya existe (el barrido de TTL). La lista
lo reusa: `ORDER BY updated_at DESC LIMIT :limit OFFSET :offset`.
Default 50, techo 100. Sin cursor: el volumen esperado es de
operadores de un solo cliente, no de un producto multi-tenant. El
día que el offset duela, el síntoma es una página lenta, no un
contrato mentiroso, y se cambia con evidencia.

Las vacías no se listan: `POST /answer/session` es perezoso a
propósito (la consola no crea fila al abrir la pantalla, sino en la
primera pregunta — y aun así hay una ventana entre el 201 y el
primer cierre). Listar esa fila sería un «Chat sin título» que el
usuario no empezó. `GET /{id}` de una sesión vacía sigue
funcionando: es el inspector de memoria, no el historial.

## 7. Qué no se mide acá

Este change no mueve el resolver ni el presupuesto. No hay nada que
correr contra el golden set. Lo que sí hay que fijar con tests, y
no a ojo:

- cinco turnos → ventana 4, history 5, respuesta 5 intacta;
- un `SearchHit` con `text` largo → el snapshot no carga `text`;
- lista: vacía y vencida afuera, orden por `updated_at`, techo de
  `limit`;
- `PATCH` 422 con título vacío; 404 con id vencido o desconocido
  (el GET de una sesión vencida ya es 404; el PATCH no inventa otra
  regla);
- el prompt `v2` y `citation_validator` no leen `history`.

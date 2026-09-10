# Diseño — memoria conversacional sobre un Q&A citado

El proyecto de referencia (`agents_event`) resuelve la ventana de contexto
con cuatro mecanismos. Copiarlos sin traducir daría un sistema peor, porque
el problema que resuelven allá no es el que tenemos acá. Este documento dice
qué se porta, con qué cambios y por qué.

---

## 1. Qué se porta de `agents_event` y qué no

| Mecanismo del curso | Acá | Por qué |
|---|---|---|
| `ProjectMetadata` re-renderizada en el system prompt cada turno | **Se porta tal cual** (como `ConversationFacts`) | Es el mecanismo más barato y el único que sobrevive a cualquier recorte, porque no vive en la historia. Cambia el contenido —filtros, códigos de transacción, documentos citados en vez de equipo y presupuesto—, no la mecánica. |
| Ventana deslizante por pares | **Se porta, más corta** (4 pares contra 6) | Allá los turnos SON el contenido. Acá compiten con la evidencia por atención y por presupuesto, y la evidencia es lo que respalda las citas. |
| Anchors que nunca se desalojan | **Se porta, con otro disparador** | Los patrones del curso (NDA, scope congelado, HIPAA) son de su dominio. El equivalente acá es una restricción de alcance que el usuario fija explícitamente. La estructura —promover el par fuera de la ventana, no desalojarlo nunca— es la misma. |
| Resumen acumulativo rolling | **Afuera por ahora** | Cuesta una llamada LLM por compactación y resuelve la pérdida de contexto lejano. Con hechos estructurados + preguntas resueltas, el contexto lejano que importa ya está en los hechos. Volver si se observa lo contrario, no antes. |
| — | **Resolución de la pregunta en el planner** (nuevo) | El curso no lo necesita: no recupera por turno. Acá es el motivo del change. Ver abajo. |

## 2. La memoria alimenta la recuperación, no solo la síntesis

Es la decisión estructural del change y la que más se aparta del modelo del
curso.

En `agents_event` la historia entra al array de mensajes de la llamada de
generación y ahí termina. Si se hiciera lo mismo acá, «¿y para siniestros?»
llegaría igual de rota al `evidence_retriever`: buscaría esa frase contra el
corpus, traería ruido, y el sintetizador —con toda la memoria del mundo en
su prompt— solo podría redactar sobre el ruido que le trajeron. La memoria
en el prompt de síntesis **no puede reparar una recuperación equivocada**.

Por eso el `query_planner` resuelve primero:

```
pregunta escrita  →  resolver(pregunta, hechos)  →  pregunta resuelta
                                                     ↓
                                            decompose → retrieve
```

Y las dos viajan en el estado y en la respuesta. Que la pregunta resuelta
sea **visible** no es cosmético: es la diferencia entre un sistema que
interpreta y uno que adivina. Si el resolver entendió mal, el usuario lo ve
en la respuesta en vez de descubrirlo por una respuesta sutilmente errónea.
Mismo criterio que `routing_history` y `agent_contributions` en
`add-answer-orchestration`: el cómo se muestra, no se infiere.

Cuando no hay sesión, o la pregunta no tiene referencias que resolver, la
resuelta es idéntica a la escrita y el camino es exactamente el actual.

## 3. Por qué la evidencia gana el presupuesto

`add-answer-context-budget` define un techo para el bloque de contexto. La
memoria se recorta **dentro** de ese techo, con su propio sub-presupuesto
(`CONVERSATION_MEMORY_MAX_TOKENS`), y el orden de descarte cuando no entra
todo es: primero la ventana de turnos, después los anchors, y los hechos
**nunca** —son ~200 tokens de campos estructurados.

Un chat genérico haría lo contrario: la conversación es el producto, la
evidencia es un adorno. Acá el producto es una respuesta citada. Un turno
viejo desplazado del prompt cuesta que el modelo repita algo; un chunk
desplazado cuesta una cita menos o una respuesta sin respaldo. No son
comparables, y el código tiene que reflejar esa asimetría en vez de dejarla
a la suerte del orden en que se concatenó.

Los hechos sobreviven siempre porque son la parte que arregla la
recuperación del turno siguiente, y ya se usaron antes de llegar al
sintetizador.

## 4. Dónde vive la sesión

**Decisión:** tabla `conversation_sessions` en Postgres.

| Alternativa | Por qué pierde |
|---|---|
| En memoria del proceso (lo que hace el curso) | Allá es deliberado y está anotado como tal: es un ejercicio. Acá la consola es una app web con recargas, pestañas y deploys; una sesión que muere en cada reinicio produce el mismo síntoma que este change viene a arreglar, de forma intermitente. Y ya tenemos Postgres y alembic — no hay infraestructura nueva que justificar. |
| Reusar el checkpointer de LangGraph | Confunde dos ciclos de vida. Un `thread_id` es **una corrida** del grafo con su pausa de revisión humana; una sesión son muchas corridas. Meter memoria de sesión en el checkpointer haría que reanudar un thread pausado reviviera hechos de un turno que ya terminó. Las tablas del checkpointer además están excluidas de alembic a propósito (`include_name` en `env.py`). |
| `session_id` generado por el cliente | Un id que el servidor no emitió es un id que el servidor no puede validar; y deja que dos pestañas compartan sesión por accidente. Emitirlo cuesta un endpoint. |

`CONVERSATION_SESSION_TTL_DAYS` acota el crecimiento. Una sesión vencida se
trata como inexistente —el turno se responde sin memoria y se dice— en vez
de fallar con 404 en la cara del usuario a mitad de una conversación.

Nota de alcance: las sesiones guardan preguntas del usuario y prosa de las
respuestas, que incluye contenido del corpus. Viven en la base, no en el
repo. Nada de esto cambia qué se versiona.

## 5. Prompt `v2`, no un parche sobre `v1`

El bloque de memoria entra en `answer/v2/{system,user}.j2`, no editando
`v1`. Es la misma razón por la que `add-answer-generation` versionó los
prompts desde el principio: el eval de fidelidad tiene que poder comparar
corridas, y una respuesta producida con memoria no es comparable con una
producida sin ella si las dos dicen «v1». La persona del perfil se sigue
appendeando **después** de las reglas, y la memoria entra **después** de la
persona y antes del contexto: ni la persona ni un turno anterior pueden
correr al modelo de la obligación de citar.

## 6. El riesgo que este change introduce

Hay que decirlo antes de construirlo: **la memoria puede contaminar la
recuperación**. Un resolver que expande «¿y eso?» hacia el referente
equivocado produce una búsqueda equivocada con más confianza que la
pregunta rota original — porque ahora *parece* una pregunta bien formada.

Tres mitigaciones, todas en el contrato y no en la esperanza:

1. La pregunta resuelta se muestra siempre que difiera de la escrita.
2. El resolver es conservador por construcción: si no hay un referente
   claro en los hechos, devuelve la pregunta tal cual. No inventa.
3. El guardrail de citas no se relaja: `citation_validator` valida contra
   los hits de este turno. La memoria nunca es procedencia.

**Y se midió, porque el riesgo se materializó.** La primera versión del
resolver matcheaba los demostrativos (`esa|ese|esos|esas`) en cualquier
posición. Corrido contra las 35 preguntas del golden set —todas
autocontenidas, así que el número correcto de reescrituras es CERO— con una
sesión activa disparó en **3 de 35 (8,6%)**: «esos boletines», «esa
cobranza», «ese pago». En las tres el demostrativo es un DETERMINANTE que
modifica a un sustantivo, no un pronombre que reemplaza a algo dicho antes.
Reescribirlas habría agregado un referente ajeno a una pregunta que ya tenía
el suyo — exactamente la falla de arriba, y encima sobre las preguntas más
largas y más caras del set.

La corrección no fue un umbral sino la regla gramatical que faltaba: los
demostrativos con género cuentan solo cuando no los sigue nada (fin de
cadena o puntuación), que es lo que los vuelve pronombres; `eso` y
`aquello` son neutros y nunca introducen un sustantivo, así que no necesitan
guarda. Después de la corrección: **0 de 35**, con la distinción fijada por
tests parametrizados en las dos direcciones.

Vale anotar por qué esto no se veía sin medir: los tests escritos a mano
usaban preguntas cortas («¿y eso?», «¿y para siniestros?») donde el
demostrativo SÍ es pronombre. El corpus real tiene preguntas de 240+
caracteres donde no lo es. Un eval sobre datos reales encontró en una
corrida lo que ninguna cantidad de casos inventados iba a encontrar.

## Lo que todavía NO está medido

El falso positivo se puede medir con el golden set porque son preguntas
autocontenidas: cualquier reescritura es un error. El falso NEGATIVO y la
calidad de la reescritura no, y hay que decirlo en vez de dejar la impresión
de que el resolver está evaluado:

- **No hay golden set multi-turno.** Las 35 preguntas son de un solo turno,
  así que no existe un dato contra el cual medir si «¿y para siniestros?»
  resuelto recupera el documento correcto.
- **El eval de fidelidad no puede correr «con memoria activa».**
  `scripts/eval_generation.py` llama a `generate_answer`, que es el camino de
  `POST /answer` — el que rechaza `session_id`. La memoria vive en el camino
  agéntico. Hacer que el eval pase por el grafo es trabajo de otro change, no
  una corrida más.

Lo que sí quedó verificado antes de archivar, y con qué: 0 reescrituras
sobre el golden set con sesión activa, 0 sin sesión, y `citation_coverage`
imposible de mover por el presupuesto (peor caso 20% del techo, ninguna
pregunta truncada — ver `add-answer-context-budget`).

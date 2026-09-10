## Why

Una respuesta cortada a mitad de palabra llegó a la consola marcada
**`grounded`, confianza 90%**, sin nada que dijera que estaba incompleta.
Reproducido contra la base real con el perfil vigente (`claude-sonnet-5`):

```
stop_reason      'max_tokens'
output_tokens    1024          <- el cap exacto
answer chars     2754          <- cortado a mitad de palabra
has closing      False         <- "Fuentes citadas" nunca se escribió
```

Hay dos defectos, y el importante no es el que se ve.

**El cap es demasiado chico, y eso se puede medir.** `ANSWER_MAX_TOKENS` vale
1024 desde `add-answer-generation`, cuando el prompt pedía una respuesta
corta con citas inline. El prompt de hoy pide una explicación continua más un
cierre de fuentes. Con el cap en 8192 —lo bastante alto como para no atar— y
sobre 8 preguntas del golden set (las 4 más largas y las 4 más cortas):

| | tokens de salida |
|---|---|
| mínimo | 626 |
| mediana | 1373 |
| máximo | 3325 |

**6 de 8 se truncan con 1024.** 3 de 8 con 2048. Ninguna con 4096. No es un
caso borde: es el comportamiento normal del servicio hoy.

**El wrapper devuelve una completion truncada como si estuviera completa, y
ese es el defecto de fondo.** `OpenAICompatibleChatLLM.complete()` nunca mira
`finish_reason`. El adaptador de Anthropic sí lee `stop_reason`, pero solo
para detectar `"refusal"`; `"max_tokens"` pasa de largo. El dato estuvo
siempre en la respuesta del proveedor y nadie lo leyó. Subir el cap sin
arreglar esto solo mueve el acantilado: la próxima pregunta más larga vuelve
a cortarse, y vuelve a hacerlo en silencio.

`AGENTS.md` §3 lo prohíbe con todas las letras: no se pierde información de
negocio sin avisar. Media respuesta sobre cómo anular una póliza, presentada
como una respuesta entera, es exactamente eso.

**Y hay un agravante nuevo.** `revise-answer-synthesis-prompt` mueve las citas
del cuerpo a un bloque `Fuentes citadas:` **al final**. Con citas inline, una
respuesta truncada al menos conservaba la procedencia de lo que alcanzó a
escribir. Ahora la procedencia es lo último que se redacta, así que es lo
primero que se pierde: el truncado pasó de degradar la respuesta a dejarla
sin respaldo. Peor todavía, `check_grounding` marca `grounded=true` cuando la
prosa no cita nada — así que una respuesta truncada antes del cierre se
presenta como **anclada** por no haber llegado a citar. Eso es lo que produjo
el badge verde de la captura.

## What Changes

- `LLM.complete()` deja de devolver `str` y devuelve `Completion(text,
  truncated)`. Un booleano al lado del texto y no una excepción: la respuesta
  parcial suele ser útil, y descartarla dejaría al usuario sin nada. Es el
  mismo criterio que ya tomó el guardrail de citas en
  `add-answer-generation` — **marcar, no rechazar**.
- Los dos adaptadores leen el motivo de corte del proveedor:
  `finish_reason == "length"` en el compatible con OpenAI, `stop_reason ==
  "max_tokens"` en Anthropic. Cada uno lo loguea y lo propaga.
- `ANSWER_MAX_TOKENS: 1024 → 4096`, con la medición de arriba como
  justificación y no como corazonada. Es un **CAP y no un objetivo**: solo se
  paga lo que se genera, así que un techo holgado no cuesta latencia ni
  tokens por sí mismo. Cubre el máximo observado (3325) con margen.
- `answer_truncated: bool` en `AnswerResponse`, `AnswerAgenticResponse`,
  `AnswerAgenticProgress` y la respuesta pausada. La consola lo muestra.
- El aviso de la consola dice qué hacer, no solo qué pasó: el tope de salida
  del perfil vigente es lo que hay que subir, y se edita en `/agents`.

**Un límite que hay que decir en vez de esconder:** el `max_tokens` guardado
en un perfil de agente **le gana** al default del servicio. Subir
`ANSWER_MAX_TOKENS` no arregla un perfil que ya tiene 1024 anotado en la
base; hay que editarlo en la consola. Este change no toca esas filas a
propósito: son configuración elegida a mano, y una migración que las pise
borraría un 1024 que alguien pudo haber puesto por una razón.

**Deliberadamente afuera (no de este change):**

- **Que el truncado dispare el gate de revisión humana.** Es tentador —una
  respuesta cortada es justo lo que un humano debería mirar— pero acopla dos
  capabilities por una condición que, con el cap medido, pasa a ser rara. Si
  aparece truncado con 4096, ahí se justifica; hoy sería gatear por algo que
  no se observa.
- **Reintentar con un cap más alto cuando el proveedor corta.** Duplica el
  costo de la pregunta más cara para recuperar una respuesta que ya está casi
  entera, y el usuario puede volver a preguntar con el perfil ajustado.
- **Derivar el cap del modelo.** Mismo argumento que en
  `add-answer-context-budget`: necesita una tabla de límites por modelo que
  hoy no existe y envejece con cada release.
- **Que `grounded` pase a false cuando hay truncado.** Son dos propiedades
  distintas y mezclarlas haría ilegibles las dos. Lo que sí queda dicho es
  que un `grounded=true` con `answer_truncated=true` no significa lo mismo
  que sin truncado, y la consola los muestra juntos.

## Capabilities

### New Capabilities
(ninguna — es una regla nueva sobre la generación que ya existe.)

### Modified Capabilities
- `answer-generation`: una completion cortada por el tope de salida se
  detecta, se reporta en el contrato y se muestra; y el tope por default pasa
  a un valor medido.
- `web-console`: la pantalla de respuesta avisa cuando la respuesta quedó
  incompleta.

## Impact

- `ai-service/app/foundation/llm/wrapper.py` — `Completion`, y los dos
  adaptadores leyendo el motivo de corte.
- `ai-service/app/config.py` — `ANSWER_MAX_TOKENS` a 4096, con la medición.
- `ai-service/.env.example` — documenta el knob y el override por perfil.
- `ai-service/app/generation/rag/answer.py` — propaga `answer_truncated`.
- `ai-service/app/generation/rag/schemas.py` — campo nuevo en `AnswerResponse`.
- `ai-service/app/domain/graph/agents/answer_synthesizer.py` — idem en el estado.
- `ai-service/app/domain/schemas.py` — `AnswerAgentState`.
- `ai-service/app/domain/graph/runner.py`, `app/api/answer_agentic.py` — contrato.
- `ai-service/tests/foundation/llm/test_wrapper.py` — los dos motivos de corte.
- `ai-service/tests/api/test_answer_router.py`,
  `tests/domain/graph/test_answer_synthesizer.py` — el campo viaja.
- `business-backend/lib/ai-service/types.ts`,
  `business-backend/app/answer/answer-console.tsx` — el aviso.
- `openspec/changes/fix-silent-answer-truncation/specs/answer-generation/spec.md`
  — delta; no se promociona a `openspec/specs/` hasta archivar.

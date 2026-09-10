# Diseño — presupuesto de contexto para la síntesis

Tres decisiones tienen alternativas reales que perdieron por razones que no
se leen en el código. El resto del change es mecánico.

---

## 1. Con qué tokenizer se cuenta

**Decisión:** reusar `count_tokens()` de `chunking/base.py` —el tokenizer de
`text-embedding-3-small`, `cl100k_base`— y tratar el resultado como una
**estimación con margen**, no como contabilidad exacta.

El servicio es multi-proveedor desde `add-multi-provider-llm`: el
sintetizador puede ser OpenAI, Anthropic o Moonshot. La contabilidad exacta
del modelo que responde no está disponible sin pagar por ella:

| Alternativa | Por qué pierde |
|---|---|
| `tiktoken.encoding_for_model(<modelo del perfil>)` | Solo cubre OpenAI. Para Anthropic y Moonshot `tiktoken` no tiene encoder, y adivinar uno da un número peor que el de un encoder consistente y conocido. |
| API de conteo de tokens de Anthropic | Una llamada de red por intento de presupuesto, en el camino caliente, para una decisión que solo necesita ser aproximada. Convierte un cálculo local en una dependencia externa que puede fallar. |
| Heurística de caracteres (`chars / 4`) | Más barata y más imprecisa. Ya tenemos `tiktoken` como dependencia y un helper probado; cambiarlo por una regla de servilleta no ahorra nada. |
| Un segundo encoder propio para generación | Dos fuentes de verdad para «cuántos tokens es este texto» en el mismo repo. La primera vez que difieran, nadie va a saber cuál mirar. |

La consecuencia hay que decirla en vez de esconderla: `cl100k_base` y el
tokenizer de un modelo no-OpenAI **no cuentan igual**. Para texto técnico en
español la diferencia observada entre familias de tokenizers está en el
orden del 10–20%, y siempre en la dirección de *más* tokens reales que los
contados. Por eso el default (16384) es holgado contra las ventanas reales
de los modelos del catálogo: el margen es el que absorbe el error del
tokenizer. Un presupuesto apretado contra la ventana exacta del modelo sería
confiar en un número que no es exacto.

Esto es también lo que hace el proyecto de referencia (`cl100k_base` fijo),
pero ahí es correcto por accidente: ese servicio es solo-OpenAI. Acá es una
aproximación deliberada y el docstring tiene que decirlo, porque el próximo
lector va a asumir exactitud si no se le avisa.

## 2. En qué orden se descarta

**Decisión:** round-robin por subconsulta; dentro de cada subconsulta, por
orden de relevancia (el que ya trae el retriever).

Hoy `evidence_retriever` acumula en un `dict` indexado por `content_hash`,
así que el orden final es **orden de inserción**: todos los hits de la
primera subconsulta, después los de la segunda, y así. Truncar la cola de
esa lista tiene un modo de fallo concreto: en «¿qué valida CA014 y qué
reporta CO001?», si la evidencia de `CA014` llena el presupuesto, la de
`CO001` desaparece **entera** y el modelo responde media pregunta con
aplomo — sin nada en la respuesta que indique que la otra mitad no tenía
respaldo.

Alternativas consideradas:

- **Ordenar la unión por `score` y cortar la cola.** Parece lo obvio y es
  incorrecto: `score` es RRF *fusionado dentro de una corrida de
  recuperación*. Dos subconsultas producen dos fusiones independientes, y
  sus puntajes no viven en la misma escala — el primero de la subconsulta B
  y el primero de la A tienen puntajes parecidos por construcción, no por
  mérito comparable. Ordenar por un número no comparable es peor que no
  ordenar, porque parece principiado.
- **Dejar el orden de inserción y solo truncar.** Es lo que hace el proyecto
  de referencia, y ahí es adecuado: su recuperación no descompone la
  consulta, así que la lista es una única corrida ordenada por distancia y
  la cola *sí* es lo menos relevante. Acá no.
- **Cuota fija por subconsulta (`budget / n`).** Desperdicia presupuesto
  cuando una subconsulta trajo dos hits y la otra doce. Round-robin degrada
  al mismo resultado en el caso simétrico y aprovecha el sobrante en el
  asimétrico.

Costo de implementación: `evidence_retriever` tiene que dejar de perder de
qué subconsulta vino cada hit. Alcanza con acumular `dict[str, list[hit]]`
por subconsulta antes de deduplicar, o con anotar el hit con su consulta de
origen. Un hit que encontraron dos subconsultas entra una sola vez, en la
posición de la primera que lo trajo.

Cuando no hubo descomposición (`sub_queries` vacío o de largo 1) el
round-robin es exactamente el orden actual: sin comportamiento nuevo en el
caso común.

## 3. Descartar y reportar, en vez de fallar

**Decisión:** el recorte no es un error. Se descartan chunks enteros, la
respuesta se produce igual, y el recorte viaja en el contrato
(`context_truncated`, `dropped_hits`).

Es la misma forma que ya tomó el guardrail de citas en
`add-answer-generation`: **marcar, no rechazar**. Un 4xx acá tiraría una
respuesta probablemente buena —los chunks que entraron son los más
relevantes— y dejaría al usuario sin nada. Pero el silencio tampoco es
opción: `AGENTS.md` §3 prohíbe perder información de negocio sin avisar, y
un chunk que no entró al prompt es información de negocio perdida para esa
respuesta.

De ahí sale la parte del change que a primera vista parece no relacionada:
**`citations` pasa a ser la evidencia presupuestada, no la recuperada.**
Hoy `answer_synthesizer` devuelve `citations = todos los hits`. Con recorte
activo eso presentaría como procedencia verificada chunks que el modelo
nunca leyó — precisamente la falla que `add-answer-generation` argumentó
como la peligrosa en este dominio. Los hits descartados no se pierden del
todo: quedan contados en `dropped_hits` y en el log, que es lo que permite
distinguir «no había evidencia» de «había, y no entró».

Partir un chunk al medio para aprovechar el presupuesto restante se
descartó sin discusión larga: los chunks son unidades funcionales
(Función/Efecto/Notas de una transacción). Medio chunk es una regla de
negocio truncada que *parece* completa, que es el peor artefacto posible en
un corpus de seguros.

## Qué queda sin resolver

`ANSWER_MAX_CONTEXT_TOKENS` es global, y el modelo del sintetizador es por
perfil. Un perfil con un modelo de ventana chica sigue pudiendo desbordar si
alguien sube el presupuesto global por encima de esa ventana. Derivar el
presupuesto del modelo necesita una tabla de ventanas por modelo —dato que
hoy no está en `providers`/`models` y que envejece con cada release del
proveedor—, así que la mitigación de este change es que el default sea
conservador y que el desborde ahora tenga un número en el log para
diagnosticarlo. Si aparece un perfil con ventana chica de verdad, ahí se
justifica el registro por modelo; hoy sería inventar un dato para un
problema que no se observó.

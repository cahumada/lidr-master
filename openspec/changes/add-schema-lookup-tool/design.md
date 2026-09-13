# Diseño

## 1. Qué es exactamente una tool, y qué no

El modelo **no ejecuta nada**. Emite un bloque `tool_use` y se detiene con
`stop_reason: "tool_use"`. Quien abre la conexión y lee el diccionario es el
servicio. El modelo pidió; no llamó.

La segunda llamada a la API lleva el **historial completo**, no solo el
resultado — la API es stateless, y sin el turno del assistant el modelo no sabe
qué preguntó:

```
[
  {role: "user",      content: "¿por qué CA014 no anula la cobertura?"},
  {role: "assistant", content: [{type: "tool_use", id: "tu_01",
                                 name: "describe_table", input: {table: "COVER"}}]},
  {role: "user",      content: [{type: "tool_result", tool_use_id: "tu_01",
                                 content: "<columnas, descripciones, relacionadas>"}]}
]
```

El `tool_use_id` ata pedido y respuesta. Es un **bucle**: con el resultado en
mano el modelo puede contestar o pedir otra tabla —típicamente una que apareció
como relacionada— y ahí se repite. Puede pedir varias en un mismo turno: varios
bloques `tool_use` en la misma respuesta, ejecutados en paralelo y devueltos como
varios `tool_result` en un único mensaje `user`.

## 2. Por qué híbrido y no reemplazo

La tentación es tirar el bloque empujado y dejar que el modelo pida todo. Pierde
por tres motivos, en orden de peso:

1. **El camino feliz deja de ser determinista.** Hoy la misma pregunta produce el
   mismo contexto. Es lo que hace comparable la eval de fidelidad y lo que
   `add-dependency-table-anchoring` defendió al mover la desambiguación a batch:
   *"la misma entrada daría distinta salida según con qué otros hits salió"*. Un
   pull puro reintroduce esa variabilidad en todas las respuestas, no solo en las
   que tienen hueco.
2. **El modelo no puede pedir lo que no sabe que existe.** Sin el bloque
   empujado, `describe_table` necesita que el modelo adivine el nombre físico de
   la tabla. El anclaje por código se lo da; la tool completa desde ahí.
3. **Latencia en el camino de todos los días.** Un bloque empujado es un
   round-trip. El bucle son dos a cuatro. Pagarlo solo cuando hay hueco es la
   diferencia entre un costo ocasional y uno permanente.

El bloque empujado queda como el camino por defecto y la tool como escape hatch.
Detrás de flag, como todo lo que este repo no midió todavía.

## 3. Por qué no MCP (todavía)

MCP no es un mecanismo distinto: es el mismo protocolo de tool use con un
transporte estándar —stdio o HTTP— encima. El cliente traduce la lista que
publica el servidor al array `tools` de la API. Mismo bucle, misma semántica.

Lo que compra MCP es que **otros clientes** consuman la capacidad: Claude
Desktop, un IDE, otro servicio. Hoy el único consumidor es `ai-service`, y el
servidor agregaría un proceso, un transporte y un contrato de versionado a
cambio de nada. Una función registrada como tool contra
`read_table_dictionary_full` da exactamente el mismo resultado.

**Cuándo se da vuelta:** el día que un segundo cliente necesite el diccionario.
Ahí el servidor MCP se escribe envolviendo la misma función, y el bucle de
`ai-service` no se entera.

## 4. Por qué el golden set es la precondición, y no un detalle de testing

`golden_transaction_tables.json` tiene hoy **4 casos** anotados a mano. Contra un
contexto determinista eso alcanza para un assert: se arma el bloque, se compara,
pasa o no pasa.

Con tool use la corrida deja de ser reproducible byte a byte. La pregunta que la
eval tiene que contestar cambia de *"¿el anclaje encontró la tabla?"* a *"¿el
modelo la pidió?"* — y esa segunda es **estadística**: varias corridas por caso,
un umbral, no un assert.

Con cuatro casos, la varianza del modelo domina. Una corrida donde tres de cuatro
aciertan y otra donde aciertan cuatro son indistinguibles de ruido. **No es que
la tool sea peor: es que no se podría demostrar que es mejor** — y este repo no
enciende un flag sin medirlo (`add-dependency-table-anchoring`: *"Sin 20 casos y
90% de recall el flag queda apagado"*).

La anotación existente **no se invalida**: las tablas que un analista nombra
siguen siendo ground truth. Lo que cambia es el harness que las puntúa.

## 5. Qué del trabajo actual sobrevive

Vale decirlo explícito, porque la pregunta que originó este change fue justamente
esa:

| Capa | Con la tool |
|---|---|
| `reader.py`, `dependencies.py`, `roles.py`, `validity.py` | **Intacta.** La tool consume `read_table_dictionary_full` igual que `resolve_context`. Sus tests siguen valiendo tal cual. |
| `resolve.py` (anclaje por código) | **Intacta** en el camino por defecto. Deja de ser la única vía. |
| `render.py` (poda por presupuesto) | **Se achica.** `DROP_ORDER` sigue, pero lo podado se vuelve recuperable a pedido. |
| `INCOMPLETE_OUTCOMES` | **Cambia de sentido.** Hoy explica *por qué no la encontré*; con la tool, también *por qué el modelo no la pidió*. |
| Inspector / `/agents/flow` | **Se rehace sobre otra cosa**: la traza de llamadas, no el bloque estático. |

La mayor parte del trabajo es la capa de lectura, y esa no se toca. Lo que este
change desplaza es específicamente **quién elige las tablas**.

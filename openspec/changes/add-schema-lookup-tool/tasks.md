# Implementation Tasks

> Diferido. El grupo 1 es precondición y **vale por sí solo**, sin el resto del
> change: mide el anclaje de hoy con más resolución.

## 1. Precondición — el set anotado (hacer primero, y solo)
- [ ] 1.1 Llevar `evals/golden_transaction_tables.json` de 4 a ~15 casos, con el
      nombre FÍSICO de la tabla y el `note` de dónde salió la anotación.
- [ ] 1.2 Correr `scripts/eval_transaction_tables.py` contra el set ampliado y
      dejar asentado el recall@N del anclaje actual como línea de base.

## 2. El protocolo LLM pasa a mensajes + tools
- [ ] 2.1 `LLM.complete(system, user)` → una firma con lista de mensajes y array
      de tools, devolviendo también los bloques `tool_use` y el `stop_reason`.
- [ ] 2.2 Implementarla en `AnthropicChatLLM`.
- [ ] 2.3 Implementarla en `OpenAICompatibleChatLLM` (formato `tool_calls`).
- [ ] 2.4 `usage_from_*` acumula el uso de todas las vueltas, no de la última.

## 3. La tool
- [ ] 3.1 `describe_table(name)` en `graph/tools.py`, sobre
      `read_table_dictionary_full`, con su esquema de entrada.
- [ ] 3.2 Nombre inexistente → resultado explícito ("no declarada"), nunca una
      excepción que corte el turno.
- [ ] 3.3 Devolver las relacionadas por el grafo, para que el modelo pueda
      encadenar sin adivinar nombres.

## 4. El bucle
- [ ] 4.1 Bucle de tool use en `answer_synthesizer`, con tope de vueltas y tope
      de tablas por turno.
- [ ] 4.2 Varios `tool_use` en una respuesta se ejecutan en paralelo y vuelven en
      un único mensaje.
- [ ] 4.3 Causa `tool_budget_exhausted` cuando se agota el tope.
- [ ] 4.4 Flag de configuración, apagado por defecto.

## 5. Traza y consola
- [ ] 5.1 `BusinessDbContext` lleva la traza: tabla pedida, vuelta, resultado.
- [ ] 5.2 `inspector.py` la expone.
- [ ] 5.3 `types.ts` y el turno de respuesta la muestran.

## 6. Medición
- [ ] 6.1 Extender `eval_transaction_tables.py` a varias corridas por caso con
      umbral, no assert exacto.
- [ ] 6.2 Reportar latencia y vueltas por turno junto al recall.
- [ ] 6.3 El flag no se enciende sin superar la línea de base del grupo 1.

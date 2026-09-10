## Qué se muestra y qué se edita

Tres capas, en este orden en el prompt compuesto:

1. **System prompt + guardrails de sistema** — el template `answer/v1`
   y `check_grounding`. Solo lectura. Quien opera tiene que verlos;
   no puede apagarlos.
2. **Persona** — voz. Ya existía. Ahora tiene un template de analista
   funcional sr. especialista en el mercado asegurador. Cargar el
   template rellena el textarea; no guarda hasta que el usuario
   confirma.
3. **Guardrails de operador** — restricciones extra del perfil, mismo
   tope que la persona. El template las presenta como bullets de
   negocio (no recomendar workarounds, separar manual/automático).
   El bloque del prompt dice que no pueden contradecir las cinco
   reglas.

## Por qué no un system prompt editable

Las cinco reglas son lo que hace comparable el eval de fidelidad. Un
textarea que las reemplace es el mismo defecto que `add-agent-profiles`
rechazó: un setting que cambia el comportamiento medido sin que el
eval se entere. Ver el prompt alcanza para auditarlo; cambiarlo es un
change de generación, con medición.

## Tools disponibles vs utilizadas

- **Disponibles (concedidas)** = `AGENT_PRIVILEGES` → `spec.tools`.
- **Utilizadas** = las que el nodo llama de verdad (`tools_used`).
  Hoy solo `evidence_retriever` usa `search_corpus`. El sintetizador
  no tiene tools: llama a un modelo.

El config también sirve un catálogo global para que la consola no
invente descripciones. Un allowlist editable en la UI seguiría
mintiendo si el dispatcher no lo aplica.

## Alternativas que perdieron

- **Meter los guardrails de operador dentro de `persona`.** Mezcla voz
  con política y no se puede mostrar un template de cada uno.
- **Hacer editables las cinco reglas.** Rompe el eval.
- **Skills como markdown.** Sería un segundo system prompt. La persona
  y los guardrails de operador cubren el pedido.

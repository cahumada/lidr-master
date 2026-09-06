# Diseño — síntesis con fuentes al final

Dos decisiones tienen alternativa real. El resto es el texto del prompt.

---

## 1. Editar `v1`/`v2` in-place, no abrir `v3`

**Decisión:** el texto de las reglas cambia dentro de las versiones que ya
existen. `v1` sigue siendo «sin memoria» y `v2` «con memoria».

| Alternativa | Por qué pierde |
|---|---|
| `v3` (reglas nuevas) + `v4` (reglas nuevas + memoria) | `add-conversation-memory` pinnea «sin sesión ⇒ `answer/v1` byte a byte». Un `v3` obliga a ese change en curso a mover el pin por un motivo que no es el suyo. El corte de versión en este repo distingue *si hubo memoria*, no *qué decían las cinco reglas*. |
| Dejar `v1` histórico y apuntar el código a `v3` | Dos templates muertos o un loader que nadie llama. El eval de fidelidad ya no es comparable con corridas viejas *en cuanto cambia el texto*; el número de versión no recupera esa comparabilidad. |

La consecuencia hay que decirla: una corrida de `eval_generation.py` con
LLM después de este change no se compara con la muestra del 2026-09-03 en
`inline_hit`. `citation_coverage` sí, porque mira `citations`, no la prosa.

---

## 2. El cierre lista lo usado, no lo recuperado

**Decisión:** `Fuentes citadas:` lleva los `document_id` de los bloques que
la explicación usó, una vez cada uno.

| Alternativa | Por qué pierde |
|---|---|
| Listar todos los hits del contexto | Duplica «Evidencia recuperada» de la consola y enseña al modelo a tratar ruido recuperado como si lo hubiera usado. |
| Seguir exigiendo `[document_id · section]` por frase | Es el defecto que este change cierra. El contrato verificable ya es `citations`. |
| Parsear el cierre en `check_grounding` en el mismo change | Mezcla un rewrite de prompt con un cambio de guardrail. Hoy «sin marcadores ⇒ grounded» ya es el comportamiento documentado; un `CA999` en el pie *sin* el patrón de corchetes no se detecta, igual que un código inventado en una oración. Ampliar el parser es un change propio si se observa invención en el cierre. |

`check_grounding` se queda. Si el modelo igual escribe un
`[ZZ999 · Función]`, `grounded` sigue siendo false. Si no escribe ninguno,
`grounded` es true — igual que hoy cuando omite marcadores.

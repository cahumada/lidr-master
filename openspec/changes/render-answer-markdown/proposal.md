## Why

El modelo escribe markdown y la consola lo muestra como texto plano. En
`business-backend/app/answer/answer-console.tsx` la respuesta se renderiza
así:

```tsx
<p className="text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
```

`whitespace-pre-wrap` conserva los saltos de línea y nada más. El resultado
es que el usuario lee literalmente `**Camino manual (CA033 / CA033_k):**`
con los asteriscos a la vista, las listas quedan como guiones sueltos, y el
cierre `Fuentes citadas:` —que el prompt `v2` pide como bloque final— no se
distingue del cuerpo.

No es solo estética. El prompt de síntesis le pide explícitamente al modelo
que **estructure**: «armá una explicación continua», distinguí Función,
Efecto, Validaciones y Campos, listá las fuentes al final en un formato
exacto. El modelo cumple y la consola tira esa estructura a la basura. Una
respuesta sobre reglas de negocio de seguros donde el procedimiento, la
excepción y las fuentes se ven todos iguales es más difícil de auditar, que
es justamente para lo que existe esta pantalla.

## What Changes

- `react-markdown` + `remark-gfm` como dependencias de `business-backend`.
  No hay ninguna librería de markdown en el proyecto hoy. `remark-gfm` entra
  por las tablas y las listas de tareas: el corpus es documentación
  funcional y el modelo reproduce tablas cuando la fuente las tiene.
- Componente `AnswerMarkdown` en `business-backend/app/answer/`, con un mapa
  de componentes explícito y estilos propios en vez de
  `@tailwindcss/typography`. El plugin traería una escala tipográfica entera
  para estilar cinco elementos, y su reset pelea con los tokens de shadcn
  que el resto de la consola ya usa.
- **Sin HTML crudo.** `react-markdown` no interpreta HTML embebido salvo que
  se le agregue `rehype-raw`, y no se agrega. El texto que se renderiza
  viene de un LLM sobre contenido de corpus; habilitar HTML sería aceptar
  markup arbitrario desde una fuente que nadie revisa.
- Los links se renderizan con `rel="noopener noreferrer"` y `target="_blank"`.
  El corpus tiene enlaces entre documentos y un link que abre en la misma
  pestaña se lleva puesto el hilo de la conversación.
- El bloque de código y las tablas scrollean en su propio contenedor. Una
  tabla ancha no puede ensanchar la burbuja del turno ni la página.
- La pregunta del usuario **no** se renderiza como markdown: es texto que
  escribió una persona, y `**` ahí es literal.
- El aviso de contexto recortado y el de pregunta resuelta siguen como
  están: son mensajes del sistema, no contenido del modelo.

**Deliberadamente afuera (no de este change):**

- Streaming de la respuesta. Sigue afuera, como en `add-answer-live-progress`.
- Resaltado de sintaxis en los bloques de código. El corpus es documentación
  funcional, no código; agregar `highlight.js` o `shiki` sería peso para un
  caso que no aparece.
- Renderizar markdown en la evidencia recuperada (`CitationList`). Ahí el
  texto del chunk se muestra a propósito **tal cual está en el corpus**,
  porque es la procedencia que alguien va a contrastar contra el documento
  original. Formatearlo lo alejaría de la fuente.
- Copiar la respuesta como markdown, o exportarla. Otro change.

## Capabilities

### New Capabilities
(ninguna — la pantalla ya existe; cambia cómo muestra lo que ya recibe.)

### Modified Capabilities
- `web-console`: la respuesta del asistente se muestra como markdown
  renderizado y no como texto plano.

## Impact

- `business-backend/package.json` — `react-markdown`, `remark-gfm`.
- `business-backend/app/answer/answer-markdown.tsx` (nuevo)
- `business-backend/app/answer/answer-console.tsx` — usa el componente para
  la respuesta completa y para la parcial de un turno pausado.
- `openspec/changes/render-answer-markdown/specs/web-console/spec.md`
  — delta; no se promociona a `openspec/specs/` hasta archivar.

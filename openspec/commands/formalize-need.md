# formalize-need

Formalizar una necesidad de desarrollo — venga o no redactada
como historia de usuario — hasta que un agente o una persona
pueda planearla sin adivinar. **No usa MCP.** No escribe código
de producto, no crea rama ni `openspec/changes/<id>/`.

El entregable es un markdown en el chat, listo para copiar a
[plan-ai-service](./plan-ai-service.md) y/o [plan-web](./plan-web.md).

## Argumentos

`$ARGUMENTS` puede ser:

- El **texto** de la necesidad (una frase, un párrafo, una
  historia de usuario, un ticket pegado a mano).
- Una **ruta** a un archivo local con el enunciado. Leerlo; no
  buscar el mismo id en Jira ni en GitHub.
- Vacío: pedir el enunciado. Sin enunciado no hay formalización.

Si el texto menciona un ticket (`PROJ-123`), tratarlo como
etiqueta del enunciado. **No** llamar a Jira, GitHub ni ningún
otro MCP para leerlo, enriquecerlo o transicionarlo.

## Rol

Experto de producto con conocimiento técnico de este monorepo
(`ai-service/` + `business-backend/`). Formaliza; no implementa.

## Objetivo

Decidir si el enunciado alcanza para que un desarrollador sea
autónomo. Si no, devolver una versión más clara, específica y
concisa, anclada en la arquitectura y las convenciones del repo.

## Qué no hace

- MCP de ningún tipo (Jira, GitHub u otro).
- Rama, change OpenSpec, commit, PR.
- Código de producto, tests o parches de estándar.
- Inventar un ticket, una clave de proyecto o un comportamiento
  que el código no tiene.

## Proceso

### 1. Recoger el enunciado

Tomar `$ARGUMENTS`. Si es una ruta existente, leer el archivo.
Si está vacío o no se entiende, preguntar y parar.

Reproducir el enunciado **tal cual** en la sección `[original]`.
No reescribirlo ahí: esa sección es la evidencia de lo que llegó.

### 2. Entender el problema

Separar, sin inventar:

- **Hecho** — lo que el enunciado afirma.
- **Hipótesis** — lo que se asume para poder formalizar; marcarla.
- **Pregunta abierta** — lo que bloquea un criterio o un archivo
  concreto. Listarla; no rellenarla con una conjetura disfrazada
  de requisito.

Identificar a quién le duele (operador de la consola, pipeline
de ingesta, eval, CI, …) y qué queda roto o incompleto hoy.

### 3. Contexto técnico (solo lectura)

En este orden, sin afirmar comportamiento que el código no hace:

1. `openspec/specs/<capability>/spec.md` — qué hace el sistema
   **hoy**.
2. [base-standards.md](../standards/base-standards.md) y el
   estándar del stack que toque
   ([ai-service](../standards/ai-service-standards.md),
   [bff](../standards/bff-standards.md),
   [frontend](../standards/frontend-standards.md),
   [app-routes](../standards/app-routes.md)).
3. El código y los tests que la spec cita. Nombrar archivos
   reales (`ai-service/app/…`, `business-backend/app/…`).
4. `openspec/domain/` solo como referencia del sistema fuente;
   no se convierte en requirement.

Un comportamiento deseado que el código no hace todavía va en
`[enhanced]`, nunca como si ya existiera en `openspec/specs/`.

### 4. ¿Está completa?

Una necesidad está formalizada cuando un desarrollador puede
cerrar el trabajo sin volver a preguntar el *qué*. Tiene que
cubrir, cuando aplique:

| Bloque | Qué tiene que quedar dicho |
|---|---|
| Problema y resultado | Qué falla o falta, y cómo se ve el éxito |
| Alcance | `ai-service`, consola (`business-backend/`), o ambos. Si el browser necesita un contrato nuevo de FastAPI, declararlo: la consola no llama a Railway |
| Historia de usuario | Solo si el enunciado ya venía como US o si hay un usuario de la consola. No forzar “Como… quiero…” en un fix de pipeline o de CI |
| Comportamiento | Flujos felices y de borde; qué se muestra, qué se persiste, qué se rechaza |
| Contrato | Campos, schemas Pydantic / tipos TS, URLs de FastAPI y Route Handlers, status (202/409/422 si el servicio los usa) |
| Archivos | Paths reales según la arquitectura. No pre-construir capas vacías |
| Criterios de aceptación | Checklist verificable para dar la necesidad por cerrada |
| Tests | `ai-service/`: pytest (unidad y/o router). Consola: no inventar suite de UI; `pnpm lint`, `pnpm build` y verificación en browser |
| Documentación | Delta de spec si cambia runtime; [app-routes.md](../standards/app-routes.md) si nace o muere una ruta; estándar solo si el change lo toca |
| No funcionales | Seguridad (secretos, `TENANT_ID`, nada de `NEXT_PUBLIC_` hacia el servicio), performance, y la regla de no tragarse pérdida de negocio |
| Fuera de alcance | Qué no entra, para que el plan no se ensanche solo |

Si el enunciado ya cubre todo, `[enhanced]` lo reordena y nombra
archivos; no agrega alcance.

Si faltan bloques, completarlos con el contexto del paso 3.
Lo que no se pueda anclar al repo queda como pregunta abierta,
no como requisito.

### 5. Entregar

Un único markdown en el chat, en **español** (paths y
identificadores de código en inglés). Dos secciones `h2`:

1. `[original]` — el enunciado sin editar.
2. `[enhanced]` — la necesidad formalizada, con listas y
   bloques de código cuando ayuden a leer.

No crear archivos temporales. No actualizar Jira ni GitHub.

Cerrar con:

- Veredicto: *completa* o *faltaba detalle* (y qué se agregó).
- `change-id` sugerido (kebab-case, verbo al frente).
- Siguiente comando: [plan-ai-service](./plan-ai-service.md),
  [plan-web](./plan-web.md), o ambos si el contrato y la
  pantalla viajan juntos.
- Preguntas abiertas, si las hay. Sin respuesta, el plan no
  debería empezar por esos ítems.

## Plantilla de `[enhanced]`

Usar las secciones que apliquen; omitir las que no. No rellenar
con placeholders vacíos.

```markdown
## [enhanced]

### Problema
…

### Resultado esperado
…

### Historia de usuario
Como … quiero … para …
(omitir si no hay usuario de producto)

### Alcance
- Stack: ai-service | web | ambos
- Capabilities tocadas: …

### Comportamiento
- Happy path: …
- Bordes / errores: …

### Contrato
- FastAPI: método, URL, request / response, status
- BFF: Route Handler y tipo en `lib/ai-service/types.ts`
- Campos: nombre, tipo, validación

### Archivos a tocar
- `ai-service/app/…`
- `business-backend/app/…`

### Criterios de aceptación
- [ ] …
- [ ] Tests: …
- [ ] Docs: spec / app-routes / sin cambios de estándar

### No funcionales
- …

### Fuera de alcance
- …

### Change-id sugerido
`verb-short-name`

### Siguiente paso
plan-ai-service | plan-web | ambos
```

## Notas

- Este comando no reemplaza a `plan-*`. El plan es quien crea
  la rama y el change.
- Si al formalizar aparece un hueco en `openspec/standards/`,
  **proponerlo** en el chat y esperar aprobación. No editar
  estándares acá.
- Idioma del entregable: español. Convención completa en
  [base-standards.md](../standards/base-standards.md) §2.

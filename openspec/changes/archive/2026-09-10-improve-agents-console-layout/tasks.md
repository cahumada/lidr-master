# Implementation Tasks

Presentación. No toca Route Handlers ni `ai-service/`.

## 1. Pantalla

- [x] 1.1 `page.tsx`: intro corta. Qué se configura acá, links a
      Flujo y Modelos. Sin párrafo técnico de `GET /config`.
- [x] 1.2 `agents-console.tsx`: picker de agentes (configurables
      primero) + workspace del seleccionado. Selección inicial = el
      primer configurable, o el primer agente si no hay.
- [x] 1.3 Perfiles de a uno: picker + un editor. Alta en el picker,
      no como card permanente. Borrar con confirmación en la UI.
- [x] 1.4 Prompt de sistema, guardrails de sistema, prompt compuesto
      y catálogo de tools en `<details>` cerrados. Tools concedidas
      vs usadas siguen visibles en el workspace del agente.
- [x] 1.5 Formulario agrupado (identidad, voz, reglas, modelo).
      Acciones a la derecha. Tokens del tema. Sin hex.

## 2. Verificar

- [x] 2.1 `pnpm lint` y `pnpm build` desde `business-backend/`.
- [x] 2.2 `python scripts/validate_specs.py` desde la raíz.
- [x] 2.3 Sin browser tools en esta sesión. `GET /agents` en
      localhost responde 307 (login). No se pudo clickear el
      picker, los perfiles ni claro/oscuro. Lint y build sí.

# Implementation Tasks

Depende de `add-llm-usage-accounting` en el servicio. Esta
rama no toca `ai-service/`.

## 1. Contrato en la consola

- [x] 1.1 Espejar en `lib/ai-service/types.ts`: `TokenUsage`
      (`input_tokens`, `output_tokens`, `total_tokens`,
      `reported`), `UsageByModel`, `UsageSummary`.
      `AnswerAgenticCompleted`, `AnswerAgenticPaused` y
      `AnswerAgenticProgress` ganan `usage?: TokenUsage`
      (ausente = el servicio viejo; no romper el parseo).
- [x] 1.2 `lib/ai-service/usage.ts` (contexto nuevo, no se
      importa desde `answer.ts`): `getUsageSummary({ from?,
      to?, session_id?, purpose? })` → `GET /usage/summary`.
      Params `from` / `to` viajan con esas claves. No
      re-declarar validación de rango.

## 2. Route Handler

- [x] 2.1 `app/api/usage/summary/route.ts` — `GET`. Reenvía
      `from`, `to`, `session_id`, `purpose` si vienen; no
      acepta `tenant_id`. `toErrorPayload` en el catch.
      422 del servicio se reenvía. 200 + ceros es éxito.

## 3. Pantalla /usage

- [x] 3.1 `app/(console)/(admin)/usage/page.tsx`: Server
      Component, `PageFrame` + `PageIntro`. Primera lectura
      `getUsageSummary()` en el server; si falla, `initial`
      nulo + `error` (no error page).
- [x] 3.2 `usage-console.tsx`: cards de
      `total_calls` / `input_tokens` / `output_tokens` /
      `total_tokens`; tabla `by_model`. Filtros `from`, `to`
      (datetime-local → ISO, mes en curso por defecto),
      `purpose` (todos / `answer` / `answer_synthesizer`) y
      `session_id` opcional (texto).
      Aplicar → `GET /api/usage/summary`. 422 → `Alert` con
      el `error` del BFF. Vacío: frase, no skeleton eterno.
      Tokens del tema, sin hex. Claro y oscuro.
- [x] 3.3 Ítem en `CONSOLE_MODULES` (módulo `configuracion`,
      `roles: ADMIN_ONLY_ROLES`, href `/usage`, title `Uso`,
      icono `BarChart3` de `lucide-react` — ya está en el
      paquete). Actualizar el comentario de `ADMIN_ONLY_ROLES`
      (hoy dice «las cuatro entradas»). Sidebar y portada
      salen de ahí.
- [x] 3.4 Filas en `openspec/standards/app-routes.md`: página
      `usage/page.tsx` y BFF `api/usage/summary/route.ts`.
      Sin cambios de `frontend-standards.md` ni
      `bff-standards.md`.

## 4. Turno en vivo

- [x] 4.1 `ChatTurn` en `answer-console.tsx` gana
      `usage?: TokenUsage`. Al cerrar un turno completed /
      paused / progress, copiar `body.usage` si viene.
      `historyToTurns` no setea `usage`.
- [x] 4.2 Si `usage.reported`, el turno muestra input /
      output / total (español, una vez). Si no, no se pinta
      la línea — un «sin contexto» no dice «0 tokens».

## 5. Verificar

- [x] 5.1 `pnpm lint` y `pnpm build` desde
      `business-backend/`.
- [x] 5.2 En el browser (claro y oscuro): `/usage` con
      servicio arriba (totales + tabla + filtro que 422);
      `/usage` con servicio sin el endpoint (aviso, no
      crash); un turno en `/answer` que llamó al modelo
      muestra tokens; un turno reabierto no inventa cifra.
- [x] 5.3 `python scripts/validate_specs.py` desde la raíz,
      sin errores.

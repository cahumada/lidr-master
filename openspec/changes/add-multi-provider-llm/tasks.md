# Implementation Tasks

## 1. OpenSpec

- [x] 1.1 `proposal.md` con la tabla de diferencias entre las tres APIs, por qué
      `temperature` es capacidad del modelo, y lo descartado con su razón.
- [x] 1.2 Delta `specs/agent-profiles/spec.md`.

## 2. Adaptadores

- [x] 2.1 `anthropic` como dependencia (`uv add`). El SDK oficial y no el wire a
      mano: es lo que pide la skill `claude-api` y lo que evita mantener la
      forma del request a mano.
- [x] 2.2 `OpenAICompatibleChatLLM` — renombrado desde `OpenAIChatLLM`, porque
      ahora también sirve a Kimi y el nombre viejo sería una mentira.
      `temperature=None` significa "no mandar el parámetro", no "mandar null".
- [x] 2.3 `AnthropicChatLLM` — `system` como parámetro, `max_tokens`
      obligatorio, texto = bloques `type == "text"` unidos, y `refusal` como
      error en vez de respuesta vacía.

## 3. Registro de proveedores

- [x] 3.1 `app/foundation/llm/providers.py`: `PROVIDER_SPECS` (id, label, wire,
      setting de clave, setting de base_url), `is_available`, `parse_catalog`
      (`proveedor:modelo`, entrada malformada se descarta con warning en vez de
      tirar el servicio), `supports_temperature`, `build_llm`.
- [x] 3.2 Clientes cacheados por proveedor; sin clave, `LLMProviderError` con
      el nombre del setting.
- [x] 3.3 La lista de modelos sin sampling es por MODELO
      (`claude-haiku-4-5` sí la acepta, `claude-sonnet-5` no).

## 4. Settings y persistencia

- [x] 4.1 `ANTHROPIC_API_KEY`, `MOONSHOT_API_KEY`, `MOONSHOT_BASE_URL`,
      `ANSWER_PROVIDER`; catálogo como pares `proveedor:modelo`.
- [x] 4.2 Columna `provider` en `agent_profiles` + migración `c0afa4f128bd`
      (el filtro `include_name` de `env.py` funcionó: el autogenerate solo
      detectó la columna, sin los drops del checkpointer).
- [x] 4.3 `resolve_agent_config` devuelve `provider`, `supports_temperature`, y
      `temperature=None` con fuente `unsupported` cuando el modelo la rechaza.
- [x] 4.4 `.env.example` con los settings nuevos y la advertencia de que los
      embeddings no son multi-proveedor.

## 5. API

- [x] 5.1 `GET /config` expone `providers[]` (con disponibilidad y el setting
      que la habilitaría) y `models[]` (con `available` y
      `supports_temperature`).
- [x] 5.2 `PUT /config/agents/{key}` valida el par: 422 si el par no está en el
      catálogo, 422 si el proveedor no tiene clave, 422 si viene proveedor sin
      modelo.
- [x] 5.3 `build_answer_llm(provider, model, ...)` y `get_answer_llm()` por
      `ANSWER_PROVIDER`.

## 6. Tests

- [x] 6.1 `tests/foundation/llm/test_wrapper.py` — los dos adaptadores contra
      dobles: `system` como parámetro, bloques unidos, no-texto salteado,
      `refusal` como error, temperatura omitida cuando es `None`.
- [x] 6.2 `tests/foundation/llm/test_providers.py` (nuevo) — registro, wire
      compartido de Moonshot, disponibilidad, parseo del catálogo (malformado y
      proveedor desconocido se descartan), capacidad por modelo, `build_llm`
      elige adaptador y descarta la temperatura.
- [x] 6.3 `tests/domain/test_profiles.py` — el par proveedor+modelo, y el
      modelo que rechaza sampling reporta `unsupported`.
- [x] 6.4 `tests/api/test_config_router.py` — proveedores listados, par
      cruzado rechazado, proveedor sin clave rechazado, proveedor sin modelo
      rechazado. Settings fijos en el fixture, para que las aserciones no
      dependan del `.env` de la máquina.

## 7. Consola web

- [x] 7.1 Tipos `ProviderConfig`, `ModelConfig`, `provider` en
      `EffectiveAgentConfig` y en `AgentProfileUpdate`.
- [x] 7.2 Tira de proveedores con su estado y el setting que falta.
- [x] 7.3 Selector agrupado por proveedor; opciones de un proveedor sin clave
      van `disabled`; los modelos sin sampling quedan anotados.
- [x] 7.4 Campo de temperatura deshabilitado —diciendo por qué— cuando el
      modelo elegido la rechaza; aviso cuando el proveedor vigente perdió su
      clave.

## 8. Documentación

- [x] 8.1 `ai-service/README.md` — sección multi-proveedor con la tabla de
      diferencias y el límite de los embeddings.
- [x] 8.2 `business-backend/README.md` — la tira de proveedores y el selector.
- [x] 8.3 `README.md` de la raíz.

## 9. Verificación

- [x] 9.1 `uv run pytest` y `uv run ruff check .` en verde (628 sin
      integración; 36 tests nuevos).
- [x] 9.2 `pnpm lint` y `pnpm build` en verde.
- [x] 9.3 `python scripts/validate_specs.py` en verde.
- [x] 9.4 Smoke real contra el servicio corriendo: `GET /config` reporta los
      tres proveedores con su disponibilidad y `supports_temperature` correcto
      por modelo (opus-5/sonnet-5 en false, haiku-4-5 en true); el selector de
      la consola agrupa y deshabilita lo no disponible; `PUT` con proveedor sin
      clave → 422 nombrando `ANTHROPIC_API_KEY`; `PUT` con par cruzado
      (`anthropic:gpt-4o`) → 422 listando el catálogo; `PUT` con par válido →
      200 con las tres fuentes en `profile`.
- [ ] 9.5 **Sin verificar contra las APIs reales de Anthropic y Moonshot**: no
      hay claves configuradas en este entorno, así que los dos adaptadores
      están probados contra dobles y contra la forma documentada del SDK, no
      contra una respuesta real. Verificarlo cuando se agreguen las claves.
- [ ] 9.6 No archivar hasta 9.5.

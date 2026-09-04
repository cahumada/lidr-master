## Why

El modelo de generación estaba clavado a OpenAI: `ANSWER_MODEL` era un string
suelto, el catálogo eran dos ids de `gpt-*`, y `get_answer_llm()` armaba un
cliente de OpenAI y nada más. El dueño del producto pidió poder usar **OpenAI,
Anthropic o Kimi (Moonshot)**.

No es solo "otro cliente HTTP": las tres APIs no son la misma forma, y una de
las diferencias rompe una feature que ya existía. Los modelos Claude de esta
generación **removieron los parámetros de sampling**: mandarle `temperature` a
`claude-sonnet-5` devuelve **400**. El perfil de agente (de
`add-agent-profiles`) tiene justamente un knob de temperatura, así que sin
tratarlo, elegir Sonnet convertía el endpoint de respuestas en uno roto.

**Depende de `add-agent-profiles` mergeado**: es el perfil por agente lo que
hace que "qué modelo" sea una decisión de runtime y no una env var.

## What Changes

### Tres proveedores, dos adaptadores

Moonshot sirve una API **compatible con OpenAI**, así que reusa ese adaptador
con otro `base_url` y otra clave. La Messages API de Anthropic sí es otra forma
y tiene el suyo:

| | OpenAI | Moonshot (Kimi) | Anthropic |
|---|---|---|---|
| adaptador | `OpenAICompatibleChatLLM` | el mismo | `AnthropicChatLLM` |
| `system` | mensaje con rol | mensaje con rol | **parámetro** del request |
| `max_tokens` | opcional | opcional | **obligatorio** |
| respuesta | `choices[0].message.content` | idem | lista de **bloques**; el texto son los `type == "text"` |
| rechazo de política | error HTTP | error HTTP | **HTTP 200** con `stop_reason == "refusal"` |

Ese último caso se levanta como error en vez de devolverse: un 200 sin texto
devuelto como `""` se leería como "el modelo no tenía nada que decir".

### `temperature` es capacidad del modelo, no del proveedor

`claude-opus-5` y `claude-sonnet-5` la rechazan; `claude-haiku-4-5` la acepta.
Por eso la lista es por **modelo** y no "anthropic no acepta temperature". El
catálogo publica `supports_temperature`, `build_llm` la descarta —logueado, no
en silencio— para el modelo que no la toma, y la consola deshabilita el campo
diciendo por qué.

### Disponibilidad antes de guardar

Un proveedor sin clave se reporta **no disponible** en `GET /config`, sus
modelos van `disabled` en el selector, y un `PUT` que lo elija se rechaza con
**422** nombrando el setting que falta. Guardarlo y que explote con 500 en la
próxima pregunta convierte un error de configuración en un incidente.

### El par viaja junto

`provider` es una **columna propia** en `agent_profiles`, no un prefijo dentro
del string del modelo: partir `proveedor:modelo` de una sola columna es un bug
de string esperando el primer id con dos puntos. La API valida el par completo,
así que `anthropic:gpt-4o` se rechaza en vez de guardarse como una combinación
que nadie puede correr.

### Deliberadamente descartado (con razón)

- **Embeddings multi-proveedor**: las 57.101 filas del corpus están en el
  espacio de `text-embedding-3-small`. Un embedding de otro proveedor no es
  comparable con ellas — cambiarlo es **reconstruir el corpus**, no un setting.
  Queda fuera y el código lo dice donde alguien lo buscaría.
- **Reranker multi-proveedor**: no es configurable por agente, así que no tiene
  perfil que leer. Entra cuando alguien lo pida, no antes.
- **Streaming y conteo de tokens por proveedor**: cada uno necesitaría su forma
  en los dos adaptadores, y no hay consumidor todavía.
- **`thinking` / `effort` de Anthropic**: son knobs reales de esa API, pero
  exponerlos exigiría que el perfil tenga campos que solo aplican a un
  proveedor. Primero que alguien los quiera.

## Capabilities

### Modified Capabilities

- `agent-profiles`: el perfil guarda el proveedor junto al modelo, el catálogo
  es por par `proveedor:modelo` con capacidades por modelo, y la validación
  rechaza pares inexistentes y proveedores sin clave.

## Impact

- `ai-service/pyproject.toml`, `uv.lock` — `anthropic` (justificado: la Messages
  API es otra forma; el SDK oficial es lo que la skill `claude-api` exige y
  evita mantener el wire a mano).
- `ai-service/app/foundation/llm/wrapper.py` — `OpenAICompatibleChatLLM`
  (renombrado desde `OpenAIChatLLM`: ahora también sirve a Kimi) y
  `AnthropicChatLLM`.
- `ai-service/app/foundation/llm/providers.py` (nuevo) — registro, catálogo,
  disponibilidad, capacidades, construcción de clientes.
- `ai-service/app/config.py` — `ANTHROPIC_API_KEY`, `MOONSHOT_API_KEY`,
  `MOONSHOT_BASE_URL`, `ANSWER_PROVIDER`, catálogo como `proveedor:modelo`.
- `ai-service/app/domain/profiles.py` — columna `provider`, resolución con
  capacidad de temperatura.
- `ai-service/alembic/versions/c0afa4f128bd_*.py` — la columna.
- `ai-service/app/api/config.py` — `providers[]`, `models[]` con capacidades,
  validación del par.
- `ai-service/app/dependencies.py` — `build_answer_llm(provider, ...)`,
  `get_answer_llm()` por `ANSWER_PROVIDER`.
- `ai-service/tests/foundation/llm/test_wrapper.py`,
  `tests/foundation/llm/test_providers.py` (nuevo),
  `tests/domain/test_profiles.py`, `tests/api/test_config_router.py`.
- `business-backend/lib/ai-service/types.ts`, `app/agents/*`, `app/api/config/*`.
- `openspec/changes/add-multi-provider-llm/specs/agent-profiles/spec.md`

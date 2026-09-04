## Why

El catálogo multi-proveedor de `add-multi-provider-llm` quedó en env vars:
agregar un modelo era editar `ANSWER_MODEL_CATALOG` y redesplegar, y cargar una
clave era editar el entorno del servicio. El dueño del producto pidió que los
modelos y las claves se carguen dinámicamente.

Son dos pedidos con perfiles de riesgo muy distintos, y conviene separarlos:

- **Modelos**: no son secretos, cambian seguido, y ya existe un endpoint en cada
  proveedor que dice cuáles sirve. Llevarlos a la base es ganancia sin
  contrapartida.
- **Claves**: hoy nunca tocan Postgres. Llevarlas a la base las mete en cada
  backup y cada `pg_dump` — y el flujo documentado de este proyecto es
  justamente dumpear la base local y restaurarla en Railway. Además el servicio
  **no tiene autenticación**, y el repo es público hasta que se evalúe.

Ese tradeoff se planteó explícitamente antes de implementar, con la
recomendación de dejar las claves en el entorno. **El dueño eligió guardarlas
en la base cifradas**, y esto lo implementa con las tres propiedades que hacen
que la elección sea defendible en vez de descuidada.

## What Changes

### Proveedores y modelos, en la base

Dos tablas: `providers` (id, label, wire, base_url, credencial, enabled) y
`provider_models` (modelo, `supports_temperature`, `visible`). Se **siembran**
del registro de código y de `ANSWER_MODEL_CATALOG` en el primer arranque, de
forma idempotente y aditiva: una instalación nueva se comporta igual que antes,
y un reinicio nunca deshace una edición hecha desde la consola.

`wire` es lo que convierte un proveedor NUEVO en una fila en vez de un cambio de
código: cualquier cosa que hable `/chat/completions` (Groq, DeepSeek, un vLLM
local) es `openai_compatible` más un `base_url`. Se valida contra los wires que
el código realmente implementa — una fila que declarara un wire que nadie
escribió sería una mentira que la consola mostraría igual.

### Catálogo dinámico desde el proveedor

`POST /config/providers/{id}/models/refresh` le pregunta al proveedor qué sirve.
Los ids nuevos llegan **ocultos**, porque el listado de un proveedor no es un
menú curado: medido acá, **OpenAI reporta 124 modelos** y valen la pena 2 —el
resto es `babbage-002`, `davinci-002`, `chatgpt-image-latest`,
`gpt-3.5-turbo-*`. La curaduría se respeta también en la escritura: elegir un
modelo oculto devuelve 422, para que ocultarlo no sea cosmético.

`supports_temperature` pasa a ser editable por fila y no solo derivado del
código: un proveedor puede sacar un modelo cuyo comportamiento el código nunca
vio, y esperar un deploy para poder registrar "este rechaza sampling" es cómo un
400 se queda roto.

### Credenciales cifradas, write-only, con el entorno ganando

`SECRETS_KEY` (Fernet, en el **entorno**) cifra lo que se guarda en
`providers.api_key_ciphertext`. Tres propiedades que el código hace cumplir:

1. **Sin master key no se guarda nada.** `SECRETS_KEY` vacía → 409. A propósito
   NO existe un camino "por ahora en texto plano": así es como un backup termina
   con claves vivas adentro.
2. **Ningún endpoint devuelve una clave.** De una guardada se ven cuatro
   caracteres. Hay un test que recorre el body de cada endpoint de proveedor
   buscándola, porque "nunca la devolvemos" es la clase de promesa que un campo
   agregado de buena fe rompe sin que nadie note.
3. **El entorno le gana a la base.** Un despliegue con gestión de secretos de
   verdad no queda sobreescrito por algo tipeado en la consola.

Rotar la master key vuelve ilegibles las credenciales guardadas: se reportan
como "sin credencial" en vez de pasarle al proveedor un valor roto.

### Deliberadamente descartado (con razón)

- **Autenticación del servicio**: es lo que *debería* preceder a un endpoint que
  escribe credenciales, y no está. Queda anotado como el límite conocido de esta
  decisión, no resuelto acá — meterlo en este change sería mezclar dos cosas que
  se revisan distinto.
- **Un GET que devuelva la clave**, ni enmascarada más allá del hint: es
  exactamente lo que este diseño existe para no tener.
- **Rotación automática de la master key** (re-cifrar todas las filas): sin un
  segundo entorno donde probarla, una migración de credenciales a ciegas puede
  dejarlas todas ilegibles. Hoy la rotación es manual y documentada.
- **Embeddings multi-proveedor**: sigue afuera, y por la misma razón — las
  57.101 filas viven en el espacio de `text-embedding-3-small`.

## Capabilities

### Modified Capabilities

- `agent-profiles`: el catálogo de proveedores y modelos pasa de settings a
  filas editables, con curaduría, refresh desde el proveedor, y credenciales
  cifradas write-only.

## Impact

- `ai-service/pyproject.toml`, `uv.lock` — `cryptography` (Fernet: cifrado
  autenticado, así un ciphertext manipulado falla en vez de descifrar a basura
  que se le manda al proveedor como clave).
- `ai-service/app/foundation/secrets.py` (nuevo) — cifrado, hint, y la regla de
  "sin master key no se guarda".
- `ai-service/app/domain/providers_store.py` (nuevo) — las dos tablas, el
  sembrado, la resolución de credencial y el insert masivo del refresh.
- `ai-service/app/foundation/llm/providers.py` — deja de ser dueño de la lista;
  queda con los wires, la semilla y el cache de clientes.
- `ai-service/app/api/config.py` — siete endpoints: catálogo, perfiles,
  proveedor, clave (PUT/DELETE), modelos (POST/PUT/DELETE) y refresh.
- `ai-service/app/domain/profiles.py` — capacidad de sampling leída de la fila
  del modelo; `synthesizer_runtime` resuelve el proveedor desde la base.
- `ai-service/app/dependencies.py` — `get_answer_llm()` queda como el camino
  solo-settings (sin base) que usa el script de eval.
- `ai-service/app/main.py` — sembrado en el lifespan, best-effort.
- `ai-service/alembic/versions/ec7c1a188b48_*.py`, `alembic/env.py`
- `ai-service/scripts/generate_secrets_key.py` (nuevo)
- `ai-service/.env.example` — reorganizado en 8 secciones, con `SECRETS_KEY` y
  la nota de que `ANSWER_MODEL_CATALOG` ahora es semilla.
- `ai-service/tests/foundation/test_secrets.py`,
  `tests/foundation/llm/test_providers.py`, `tests/api/test_config_router.py`
- `business-backend/app/agents/providers-panel.tsx` (nuevo),
  `app/agents/agents-console.tsx`, `app/api/config/providers/**`,
  `lib/ai-service/{config,types,base-client}.ts`
- `openspec/changes/add-dynamic-providers/specs/agent-profiles/spec.md`

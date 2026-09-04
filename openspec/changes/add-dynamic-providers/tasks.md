# Implementation Tasks

## 1. OpenSpec

- [x] 1.1 `proposal.md` separando los dos pedidos (modelos vs claves) con sus
      perfiles de riesgo, la decisión del dueño, y lo descartado con su razón.
- [x] 1.2 Delta `specs/agent-profiles/spec.md`.

## 2. Cifrado

- [x] 2.1 `cryptography` vía `uv add` (Fernet: cifrado autenticado, así un
      ciphertext manipulado falla en vez de descifrar a basura).
- [x] 2.2 `app/foundation/secrets.py`: `SECRETS_KEY` del entorno, `encrypt`,
      `decrypt`, `hint` (cuatro caracteres), `is_enabled`. **Sin master key no
      se guarda nada** — no existe camino a texto plano.
- [x] 2.3 `SecretsCorrupted` para el ciphertext ilegible (clave rotada o dump
      de otro entorno): se reporta, no se le pasa un valor roto al proveedor.
- [x] 2.4 `scripts/generate_secrets_key.py` — imprime y no guarda.

## 3. Tablas

- [x] 3.1 `app/domain/providers_store.py`: `ProviderRow` (con
      `api_key_ciphertext` + `api_key_hint`) y `ProviderModelRow` (con
      `supports_temperature` + `visible`), `ResolvedProvider`,
      `resolve_provider` (entorno gana), `ProviderRepository`.
- [x] 3.2 `seed_if_empty` idempotente y aditivo, llamado en el lifespan;
      best-effort, porque un servicio que no responde nada por no poder
      escribir una fila de catálogo es peor que uno que reporta el proveedor
      como no disponible.
- [x] 3.3 Migración `ec7c1a188b48`. El filtro `include_name` siguió andando:
      autogenerate detectó solo las tablas nuevas, sin los drops del
      checkpointer.
- [x] 3.4 `upsert_models` masivo. **Medido:** el loop de a uno colgó el refresh
      (3 round-trips × 124 modelos contra la base por el proxy público);
      con un solo statement responde al instante.

## 4. Registro y resolución

- [x] 4.1 `providers.py` deja de ser dueño de la lista: quedan los wires, la
      semilla, `supports_temperature_default`, el cache de clientes por
      (wire, base_url, clave) y `list_provider_models`.
- [x] 4.2 `build_llm_for(resolved, ...)` rechaza proveedor deshabilitado o sin
      credencial, y descarta la temperatura que el modelo no acepta.
- [x] 4.3 `effective_config_for` lee la capacidad de la fila del modelo, con
      fallback a lo que sabe el código para un modelo sin registrar.
- [x] 4.4 `get_answer_llm()` queda como el camino SOLO-settings, sin base, que
      usa `scripts/eval_generation.py`.

## 5. API

- [x] 5.1 `GET /config` con `providers[]` (wire, key_source, hint, enabled,
      model_count), `models[]` (visible, capacidad) y
      `credential_storage_enabled`.
- [x] 5.2 `PUT /config/providers/{id}` — label, base_url, note, enabled. La
      credencial NO va acá: mezclarla haría que un formulario que edita un
      label lleve un secreto.
- [x] 5.3 `PUT`/`DELETE /config/providers/{id}/key` — write-only; 409 sin
      master key. No hay GET.
- [x] 5.4 `POST`/`PUT`/`DELETE` de modelos + `POST .../models/refresh`.
- [x] 5.5 Validación del par contra las filas, rechazando modelo oculto.

## 6. Tests

- [x] 6.1 `tests/foundation/test_secrets.py` — sin master key no se guarda,
      round-trip, el ciphertext no contiene el plaintext, dos cifrados del
      mismo valor difieren, clave equivocada lanza, el hint revela cuatro.
- [x] 6.2 `tests/foundation/llm/test_providers.py` reescrito a wires + semilla
      + `build_llm_for`.
- [x] 6.3 `tests/api/test_config_router.py` con los dos stores falseados,
      incluido **un test que recorre el body de cada endpoint de proveedor
      buscando la clave**.
- [x] 6.4 Settings fijos en el fixture, para que las aserciones no dependan del
      `.env` de la máquina.

## 7. Consola web

- [x] 7.1 Tipos: `ProviderConfig` con wire/key_source/hint, `ModelConfig` con
      `visible`, `ServiceConfig` con `credential_storage_enabled` y `wires`.
- [x] 7.2 `lib/ai-service/config.ts` con los siete clientes; `deleteNoContent`
      en el base client para el 204.
- [x] 7.3 Route Handlers bajo `app/api/config/providers/**`. El de la clave no
      loguea el body y no tiene GET.
- [x] 7.4 `app/agents/providers-panel.tsx`: credencial write-only (input
      `type="password"`, sin valor precargado), toggle de habilitado, base URL
      para los wires OpenAI-compatible, curaduría de modelos y "Traer del
      proveedor". Relectura completa tras cada cambio.

## 8. Documentación

- [x] 8.1 `.env.example` reorganizado en 8 secciones + `SECRETS_KEY` +
      `ANSWER_MODEL_CATALOG` marcado como SEMILLA. Chequeado mecánicamente
      contra `Settings`: ninguna variable obsoleta, ninguna perdida.
- [x] 8.2 `ai-service/README.md` — proveedores en la base, refresh, y las tres
      propiedades de las credenciales **con el tradeoff dicho de frente**.
- [x] 8.3 `business-backend/README.md` y `README.md` de la raíz.

## 9. Verificación

- [x] 9.1 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
- [x] 9.2 `pnpm lint` y `pnpm build` en verde desde `business-backend/`.
- [x] 9.3 `python scripts/validate_specs.py` en verde.
- [x] 9.4 Smoke real contra el servicio y la consola corriendo: el sembrado
      creó los 3 proveedores y 7 modelos; `GET /config` reporta OpenAI con
      `key_source=env` y los otros dos sin credencial; guardar clave sin
      `SECRETS_KEY` → 409; proveedor inexistente → 404; **refresh real contra
      OpenAI → 124 modelos reportados, guardados ocultos**; ocultar `gpt-4o`
      por el proxy de Next → desaparece de los ofrecidos y elegirlo → 422;
      revertido.
- [ ] 9.5 **Sin verificar contra las APIs reales de Anthropic y Moonshot**: no
      hay claves en este entorno. El refresh y la generación de esos dos están
      probados contra dobles, no contra una respuesta real.
- [ ] 9.6 **Límite conocido de esta decisión**: el servicio no tiene
      autenticación, así que el endpoint que escribe credenciales lo puede
      llamar cualquiera que lo alcance (escribir, no leer). Autenticar el
      servicio es su propio change y debería preceder a exponer esto en
      internet.
- [ ] 9.7 No archivar hasta 9.5 y 9.6.

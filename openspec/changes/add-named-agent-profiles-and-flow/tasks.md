# Implementation Tasks

## 1. OpenSpec

- [x] 1.1 `proposal.md` con el mapeo al curso (perfil nombrado ≠ nodo) y
      lo descartado con su razón.
- [x] 1.2 `design.md` con el modelo, la resolución por corrida y por qué
      no hay editor de grafo.
- [x] 1.3 Deltas de `agent-profiles`, `web-console` y
      `answer-orchestration`.

## 2. Persistencia

- [x] 2.1 Migrar `agent_profiles`: PK surrogate, `name`, `is_default`,
      unique `(agent_key, lower(name))`. La fila anónima existente se
      copia a un perfil default `"Default"`; sin fila no se inventa
      ninguna.
- [x] 2.2 `AgentProfileRepository`: list/get/create/update/delete por
      `agent_key` + id; `ensure_single_default`; borrar el default
      promociona otro o deja al agente en Settings.
- [x] 2.3 `resolve_agent_config` sigue mergeando knobs nulos sobre
      Settings. Nuevo helper: resolver por `profile_id` o por default
      del sintetizador.
- [x] 2.4 Tests de merge, default único, nombre duplicado, migración de
      la fila anónima.

## 3. API de perfiles y catálogo

- [x] 3.1 `GET /config` lista `profiles` por agente configurable y
      marca el default. Agentes deterministas no llevan lista.
- [x] 3.2 `POST /config/agents/{key}/profiles` crea; `PUT …/{id}`
      reemplaza; `DELETE …/{id}` borra. 404 agente desconocido o perfil
      ajeno; 422 determinista / modelo oculto / persona sobre el tope /
      nombre vacío.
- [x] 3.3 El `PUT /config/agents/{key}` anónimo actual deja de escribir
      la fila única: o se retira, o se documenta como alias que actualiza
      el default. Elegir uno y testearlo — no dejar los dos semánticas.
- [x] 3.4 `GET /config` incluye `flow`: nodos, `kind`, aristas de
      `build.py` y `ladder` de `_ORDER`.
- [x] 3.5 Test de drift: `flow` coincide con el grafo compilado y con
      `_ORDER`.

## 4. Resolución en una corrida

- [x] 4.1 `synthesizer_runtime` acepta `profile_id` opcional; ausente =
      default; id de otro agente o inexistente = error de dominio que el
      router traduce a 422.
- [x] 4.2 `AnswerRequest` y el body agentico llevan `profile_id`
      opcional. Los tres caminos (`/answer`, `/answer/agentic`, runner)
      pasan por el mismo helper.
- [x] 4.3 Tests: default aplica sin id; id válido cambia persona/modelo;
      id ajeno es 422; sin perfiles el prompt sigue byte-idéntico.

## 5. Consola — perfiles nombrados

- [x] 5.1 Tipos en `lib/ai-service/types.ts` + cliente de CRUD.
- [x] 5.2 Route Handlers proxy de create/update/delete (la validación
      queda en el servicio).
- [x] 5.3 `/agents`: lista de perfiles del sintetizador (nombre, default,
      modelo vigente); alta, edición, «usar como default», borrar.
      Deterministas siguen read-only con tools y rol.
- [x] 5.4 `/answer` permite elegir el perfil del sintetizador para esa
      corrida; vacío = default.

## 6. Consola — flujo

- [x] 6.1 `/agents/flow` renderiza diagrama + tabla desde `config.flow`,
      no desde un array local. Badge por `kind` (agente / supervisor /
      gate).
- [x] 6.2 Nav: Agentes y Flujo bajo Configuración. Portada actualizada.
- [x] 6.3 Si el servicio no responde, la pantalla lo dice — no inventa
      nodos.

## 7. Verificación

- [x] 7.1 `uv run pytest` y `uv run ruff check .` desde `ai-service/`.
- [x] 7.2 `pnpm lint` y `pnpm build` desde `business-backend/`.
- [x] 7.3 `python scripts/validate_specs.py` desde la raíz.
- [x] 7.4 Smoke: migración aplicada; `GET /config` sirve 6 nodos + 11
      aristas; alta de Conservador/Exhaustivo; `profile_id` inválido →
      422; `/agents` y `/agents/flow` renderizan esos datos. Sin
      herramientas de browser: no se clickeó el formulario ni se mandó
      una pregunta real con el selector del chat.

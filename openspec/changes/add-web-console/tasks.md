# Implementation Tasks

Depende de `move-service-to-ai-service`: hasta que el servicio esté en
`ai-service/`, el §5 (Dockerfile) y el §6 (filtros de CI) no tienen dónde
apoyarse.

## 1. Scaffolding de `business-backend/`
- [x] 1.1 `create-next-app` en `business-backend/` — TypeScript, App Router,
      Tailwind, ESLint.
- [x] 1.2 Inicializar shadcn/ui. Copiar **solo** los componentes que las
      pantallas usan (`button`, `input`, `card`, `badge`, `table`, `switch`,
      `select`, `alert`) — no el catálogo entero.
- [x] 1.3 `business-backend/.env.example` con `AI_SERVICE_URL` y nada más.
      Sin prefijo `NEXT_PUBLIC_`: si el browser la puede leer, el diseño se
      rompió.
- [x] 1.4 Layout base con la navegación de las tres pantallas.

## 2. La capa que habla con el servicio IA
- [x] 2.1 `lib/ai-service/base-client.ts`: `fetch` contra `AI_SERVICE_URL`,
      timeout, y el mapeo de errores del servicio a errores propios
      (`AiServiceError`, con los 409/400 de `/corpus/rebuild` distinguibles).
      Es la única capa del proyecto que hace HTTP hacia FastAPI.
- [x] 2.2 `lib/ai-service/types.ts`: tipos que espejan 1:1 los schemas de
      `ai-service/app/generation/rag/schemas.py` (`SearchResponse`,
      `SearchHit`, `Chunk`, `ChunkMetadata`, `IngestStats`) y de
      `app/ingestion/schemas.py` (`IngestionJob`, `RebuildRequest`,
      `RebuildStarted`). A mano y no con un generador de OpenAPI: son seis
      formas, y un generador agrega una dependencia y un paso de build para
      mantener algo que cambia cada varias semanas.
- [x] 2.3 Un cliente por contexto: `search.ts`, `documents.ts`, `corpus.ts`.
      Los contextos no se importan entre sí.

## 3. Route Handlers (el proxy)
- [x] 3.1 `GET /api/search` → reenvía los query params a `{AI_SERVICE_URL}/search`.
- [x] 3.2 `POST /api/documents/ingest-file` → reenvía el multipart.
- [x] 3.3 `POST /api/corpus/rebuild`, `GET /api/corpus/jobs`,
      `GET /api/corpus/jobs/[id]` → reenvían tal cual, **incluidos los códigos
      409 y 400**: el guard vive en el servicio, el proxy lo transporta sin
      reinterpretarlo.
- [x] 3.4 Verificar que ninguna respuesta ni ningún bundle de cliente contiene
      `AI_SERVICE_URL` (grep sobre `.next/static` después de un build).

## 4. Pantallas
- [x] 4.1 **Búsqueda**: formulario (`q`, `module_code`, `window_type_name`,
      `limit`, toggles `lexical`/`split`/`rerank` con su número medido al
      lado) + resultados con procedencia completa (documento, título, sección,
      score, ramas) + las sub-preguntas cuando `split` está activo.
- [x] 4.2 **Vista previa de ingesta**: subir un `.md` → chunks y estadísticas.
      Sin botón de guardar: esa operación no existe en el servicio.
- [x] 4.3 **Reconstrucción de corpus**: selección de pasos
      (`chunk`/`embed`/`load`), guard de `reset` con confirmación de
      `tenant_id`/`doc_version` **leídos del servicio**, lista de jobs
      recientes, y polling del job activo mostrando `current_step`,
      `progress`, `status` y `error`.
- [x] 4.4 **Home**: enlaza las tres. Sin métricas en vivo — ningún endpoint las
      expone (ver `design.md`).

## 5. Despliegue del servicio IA (Railway)
- [x] 5.1 `ai-service/Dockerfile`: `uv sync --frozen`, `uvicorn app.main:app`.
- [x] 5.2 `ai-service/.dockerignore`: `data/`, `.venv/`, `evals/`, `tests/`.
- [ ] 5.3 Proyecto Railway: root directory `ai-service/`, healthcheck
      `/health` (ya existe en `app/main.py`), variables `DATABASE_URL`,
      `OPENAI_API_KEY`, `TENANT_ID`, `DOC_VERSION`, `CORPUS_ROOT` si aplica.
- [ ] 5.4 Railway "Watch Paths" = `ai-service/**`, para que un commit en
      `business-backend/` no dispare un redeploy.
- [x] 5.5 Documentarlo en el `README.md` de la raíz.

## 6. Despliegue de la app web (Vercel)
- [ ] 6.1 Proyecto Vercel: root directory `business-backend/`, variable
      `AI_SERVICE_URL` con la URL pública de Railway.
- [ ] 6.2 "Ignored Build Step" que salte el build cuando el commit no toca
      `business-backend/`.
- [x] 6.3 Documentarlo en el `README.md` de la raíz.

## 7. CI
- [x] 7.1 `.github/workflows/ci.yml`: job `changes` con `dorny/paths-filter`
      (`ai-service`, `business-backend`).
- [x] 7.2 Job del servicio IA: `uv sync --frozen`, `ruff check .`, `pytest -q`,
      `working-directory: ai-service`, condicionado al filtro.
- [x] 7.3 Job de la app web: `npm ci`, `npm run lint`, `npm run build`,
      `working-directory: business-backend`, condicionado al filtro.
- [x] 7.4 Ningún job de deploy (§5, §6).
- [ ] 7.5 Chequeo de contrato entre `types.ts` y los schemas Pydantic, al
      estilo del `check_contract.py` del curso. **La justificación llegó sola:**
      los tipos se escribieron a mano contra el código Python y ya nacieron
      desincronizados — `ChunkedDocument.is_container` faltaba y `Reference`
      declaraba `kind: string` donde el servicio devuelve `type` y `context`.
      Lo detectó comparar las claves de una respuesta real contra el tipo, a
      mano; eso es exactamente lo que un job puede hacer solo. Decidir si se
      compara contra el `openapi.json` del servicio o contra una respuesta
      grabada.

## 8. Documentación
- [x] 8.1 `openspec/project.md`: la stack de `business-backend/` (Next.js,
      Tailwind, shadcn/ui), la regla de que una sola capa habla HTTP con el
      servicio IA, y la condición de entrada del Vercel AI SDK.
- [x] 8.2 `README.md` de la raíz: cómo correr las dos apps en local y cómo se
      despliega cada una.
- [x] 8.3 `AGENTS.md` §4: los comandos de `business-backend/`.

## 9. Verificación
- [x] 9.1 `npm run lint` y `npm run build` en verde.
- [x] 9.2 Desde `ai-service/`: `uv run pytest` y `uv run ruff check .` siguen
      en verde (este change no debería tocar nada del servicio; si algo falla,
      es que sí lo tocó).
- [x] 9.3 `python scripts/validate_specs.py` en verde.
- [x] 9.4 Smoke local: las tres pantallas contra
      `uv run uvicorn app.main:app --reload`, incluido el camino de error
      (apagar el servicio y confirmar que la UI dice qué pasó, sin traza cruda).
- [ ] 9.5 Smoke post-deploy: las tres pantallas en Vercel contra Railway.
- [ ] 9.6 Confirmar los dos filtros de despliegue con commits reales: uno que
      toque solo `business-backend/` (no debe redesplegar Railway) y uno que
      toque solo `ai-service/` (no debe redesplegar Vercel).
- [ ] 9.7 Promover el delta de `web-console` a `openspec/specs/` y archivar.

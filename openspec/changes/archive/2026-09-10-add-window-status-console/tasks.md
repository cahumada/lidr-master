# Implementation Tasks

Depende de `add-window-status-metadata` en el servicio (ya en
`main`). Esta rama no toca `ai-service/`. No se reenvía
`window_status` como filtro: el contrato no existe.

## 1. Contrato en la consola

- [x] 1.1 En `lib/ai-service/types.ts`, agregar
      `window_status: string | null` a `SearchHit` y a
      `ChunkMetadata`, con el mismo comentario bilingüe que el
      `Field` de `ai-service/app/generation/rag/schemas.py`. No
      agregar `document_kind` ni otros campos atrasados en el
      mismo diff.
- [x] 1.2 No tocar `SearchParams`, `SearchFacets` ni
      `AnswerRequest`: el servicio no acepta el filtro. No tocar
      `CitationSnapshot`.

## 2. Badge compartido

- [x] 2.1 `components/window-status-badge.tsx`: si
      `window_status` está ausente o es `Activo`, no renderiza
      nada. Si está resuelto y no es `Activo`, un `Badge` con el
      **nombre declarado** (nunca "baja", nunca el código `3`).
      Tokens del tema (`variant="outline"` o equivalente); sin
      hex. Acepta `string | null | undefined` para degradar si el
      servicio viejo omite el campo.

## 3. Pantallas

- [x] 3.1 `app/(console)/search/search-console.tsx`: `Hit` monta
      el badge junto a `document_id` / módulo. No se agrega
      filtro. El grid de filtros sigue en dos listados.
- [x] 3.2 `app/(console)/answer/answer-console.tsx`: `CitationView`
      gana `window_status?: string | null`. `CitationList` monta
      el badge. Al copiar citas en vivo desde el payload, pasar el
      campo. `historyToTurns` / `snapshots` **no** inventan
      estado.
- [x] 3.3 `app/(console)/documents/ingest-console.tsx`: la vista
      previa muestra el badge cuando el chunk (o el documento, si
      se pinta a ese nivel) trae un estado no vigente. La tabla
      no gana una columna vacía para los vigentes.
- [x] 3.4 Sin ítem nuevo en `CONSOLE_MODULES`. Sin fila nueva en
      `openspec/standards/app-routes.md`.

## 4. Verificar

- [x] 4.1 `pnpm lint` y `pnpm build` desde `business-backend/`.
- [x] 4.2 En el browser (claro y oscuro): buscar una transacción
      con `Acceso restringido` (p. ej. la del golden
      `U-MGSL006-acceso-restringido`) y ver el badge; buscar una
      vigente y **no** ver badge de estado; abrir `/answer` y
      comprobar la cita en vivo; reabrir un historial y comprobar
      que no aparece un estado inventado; subir un `.md` en
      `/documents` de una transacción no vigente y ver el badge
      en la vista previa.
      > Verificado por el dueño del repo el 2026-09-10. El agente no pudo ejercerlo: la consola exige login y no puede autenticarse.
- [x] 4.3 `python scripts/validate_specs.py` desde la raíz, sin
      errores.

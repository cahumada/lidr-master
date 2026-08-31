# Tareas de implementación

## 1. Estructura y convenciones

- [x] 1.1 Verificar la arquitectura real del curso contra la rama `session_16`
      de LIDR-academy/ai-engineering (el servicio vive en `ai-service/`,
      renombrado desde `estimator/` en la sesión 15).
- [x] 1.2 Crear la raíz de composición: `app/config.py` (Settings +
      `get_settings()` cacheado), `app/dependencies.py` (singleton del chunker
      por DI), `app/main.py` (app FastAPI + `configure_logging()` con structlog).
- [x] 1.3 Ubicar los contratos en `app/generation/rag/schemas.py` y las
      estrategias en `app/generation/rag/chunking/`, espejando el layout del curso.
- [x] 1.4 Aplicar la convención de código: identificadores en inglés,
      docstrings y comentarios bilingües `EN || ES`, incluidos los
      `Field(description=...)` que se publican en Swagger.
- [x] 1.5 `pyproject.toml` con fastapi, pydantic, pydantic-settings, structlog,
      tiktoken, python-multipart; dev: pytest, httpx, ruff.

## 2. Normalizador y reparación de tablas

- [x] 2.1 `normalize_line_endings`: `\r\n` y `\r` → `\n` antes de cualquier parseo.
- [x] 2.2 Detección de bloques candidatos: dos o más `####` consecutivos
      seguidos inmediatamente de líneas con `|`.
- [x] 2.3 Reconstrucción de la forma **simple** (headers + filas `etiqueta | valor`).
- [x] 2.4 Reconstrucción de la forma **pareada** (headers + etiqueta como
      `####` + línea `| valor`), encontrada en CA001 y no descrita en el pedido inicial.
- [x] 2.5 Relleno con `""` + `logger.warning` + advertencia en el registro
      cuando una fila trae menos celdas que columnas.
- [x] 2.6 `RepairedTable` con el bloque original crudo, para trazabilidad.
- [x] 2.7 No disparar con un `####` real seguido de prosa (test negativo).

## 3. Chunker

- [x] 3.1 Extracción del `document_id` tolerante a `(CA014)` / `**(CA001k)**`,
      restringida al bloque de título para no confundir referencias a otros documentos.
- [x] 3.2 Extracción del título con fallback a la primera línea no vacía
      (CA014 no tiene `# `).
- [x] 3.3 Chunking Tipo A: una fila de tabla = un chunk, con celdas etiquetadas
      por su columna y `metadata.field`.
- [x] 3.4 Chunking Tipo B: bullet de primer nivel con sus hijos, descenso
      recursivo bajo techo de tokens, fallback por oración y por palabra.
- [x] 3.5 Contextual header en todo chunk, con `bullet_path` cuando aplica.
- [x] 3.6 Extracción de tablas embebidas en secciones narrativas.
- [x] 3.7 Referencias cruzadas en una sola lista con discriminador
      (`inline_transaction` / `footnote_tag`), excluyendo el id propio.
- [x] 3.8 `token_count` con `tiktoken.encoding_for_model("text-embedding-3-small")`.
- [x] 3.9 **Fix**: calcular el presupuesto de tokens por nodo desde su propio
      header, no una vez al tope — el `bullet_path` crece al descender y dejaba
      pasar chunks de 505/512/527 tokens en CA014.
- [x] 3.10 Generalizar la detección de secciones a cualquier H2 y decidir la
      estrategia por forma del contenido, para cubrir los 30 módulos.
- [x] 3.11 Slug de `chunk_id` derivado del heading + contador por slug para
      documentos con headings repetidos.

## 4. API

- [x] 4.1 `POST /documents/ingest` con body JSON tipado.
- [x] 4.2 `POST /documents/ingest-file` con `UploadFile`, decodificado como
      UTF-8, `400` si no lo es — para poder probar desde Swagger con el botón
      nativo de archivo.
- [x] 4.3 Un solo cuerpo compartido (`_ingest`) entre ambos endpoints.
- [x] 4.4 `500` con mensaje genérico al cliente y detalle logueado ante falla.
- [x] 4.5 **Fix**: `ChunkMetadata` e `IngestStats` como modelos anidados en vez
      de `dict`, para que Swagger declare los atributos reales en la pestaña Schema.
- [x] 4.6 `GET /health` sin efectos secundarios.

## 5. Tests

- [x] 5.1 `test_normalizer.py`: los 3 fixtures reales de tabla rota (CA014
      "Ramos generales", las 2 tablas "Tipo de registro" de CA001, las 5 filas
      "Tipo de inicio de vigencia" de CA001), más el caso negativo y el de relleno.
- [x] 5.2 `test_functional_spec_chunker.py` sobre los 3 documentos reales:
      techo de tokens, 1 chunk por fila de `Campos`/`Validaciones` (recontado
      de forma independiente desde la fuente), contextual header, `token_count`
      consistente, referencias `CAC011`/`DF009` con su tipo, y sin auto-referencia.
- [x] 5.3 Verde: 26 tests, `ruff check .` limpio.

## 6. Corrida batch

- [x] 6.1 `scripts/chunk_corpus.py`: descubrimiento recursivo agrupado por
      módulo, filtro `--modules`, exclusión de la documentación del proyecto
      en la raíz del corpus.
- [x] 6.2 Aislamiento de fallas: un archivo ilegible o que lanza excepción se
      registra y la corrida sigue.
- [x] 6.3 Salida: un JSON por módulo + `chunking_report.md` con tabla por
      módulo y listado individual de archivos en cero chunks y fallidos.
- [x] 6.4 Corrida completa verificada: 2169 archivos → 67.121 chunks, 5.449.651
      tokens, 14,3 s, 0 fallos, 2 archivos en cero chunks (ambos por fuente
      corrupta: uno vacío, otro HTML de Word en UTF-16 con extensión `.md`).

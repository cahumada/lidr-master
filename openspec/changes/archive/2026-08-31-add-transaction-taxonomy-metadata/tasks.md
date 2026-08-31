# Tareas de implementación

## 0. Regex de id: cubrir las formas reales (causa raíz)

- [x] 0.1 Extender el reconocimiento de id para cubrir los códigos que no veía:
      sufijo con guion bajo (`BC005_k`, `VI7501_A`), códigos sin dígitos
      (`MENU`), y dígitos + guion (`CA13-1`). Antes exigía `[A-Z]{2,4}\d{3}[a-z]?`.
      Resuelto con dos patrones: `ID_LINE_PATTERN` (línea de id sola,
      permisivo) y `DOCUMENT_ID_PATTERN` (fallback inline, exige dígitos para
      que `(CAE)` / `(PAE)` en prosa no se confundan con ids).
- [x] 0.2 Cubrir las 4 formas de bloque de id observadas: `` `**(CODE)**` ``
      (336 casos), `` **`(CODE)`** `` (24), `` `(CODE)` `` (2), y la malformada.
      Se agregó una quinta forma real encontrada al implementar:
      `` \(`CODE`\) `` (paréntesis escapados afuera, backticks adentro).
- [x] 0.3 Test tabla-dirigido con los códigos reales del corpus, incluidos los
      que fallaban, más casos negativos de prosa.
- [x] 0.4 Verificado que ampliar el patrón no genera falsos positivos.
      Resultado sobre los 2169 archivos: **18 ids corregidos**, 0 ids nuevos sin
      forma de código de transacción. Los 3 casos que parecían sospechosos son
      lo que el documento realmente declara (ver `design.md` §7).

## 1. Atribución por transacción en archivos multi-transacción

- [x] 1.1 Segmentar el documento por **líneas de id**, no por bloques `# ` (H1).
      Cambio respecto de lo propuesto: H1 resultó no ser un delimitador
      confiable — el export emite `# ` también para líneas de continuación de
      bullets (`# · _Adicionalmente..._`, `# § _Se construye..._` en
      `accounting/cp002.md`), así que partir por H1 inventaba bloques. Cada
      línea de id se extiende hacia atrás al H1 más cercano, sin cruzar la
      línea de id anterior.
- [x] 1.2 Resolver el `document_id` por bloque, buscando el bloque de id en el
      texto previo al primer `## ` **de ese bloque** (se reutilizó la regla de
      `extract_document_id`, no un parser nuevo).
- [x] 1.3 Tratar un bloque sin id propio, en un archivo donde otros sí lo
      tienen, como contenedor. Refinamiento hallado al implementar: cuando el
      código del contenedor coincide con uno de los bloques declarados, el
      preámbulo **es** la introducción de esa transacción y se fusiona con
      ella; solo se conserva como contenedor marcado cuando no coincide con
      ninguno (4 casos en todo el corpus).
- [x] 1.4 Tomar el código del **contenido** como autoritativo y dejar el nombre
      de archivo solo como fallback (`resolve_file_level_code`).
- [x] 1.5 `chunk()` devuelve `list[ChunkedDocument]` en vez de una tupla
      `(id, title, chunks)`; `app/api/documents.py` y `scripts/chunk_corpus.py`
      actualizados. `IngestResponse` pasa a `source_file` + `documents[]`.
- [x] 1.6 Test de regresión con `clients/bc005.md`: los chunks de
      `Campos`/`Validaciones` de `BC005_k` llevan `document_id='BC005_k'` y los
      de `BC005` llevan `BC005` — antes los 53 quedaban como `BC005`.
- [x] 1.7 El par `<CODIGO>` / `<CODIGO>_k` queda vinculado vía
      `parent_transaction_code`, solo cuando el código base está declarado en
      el mismo archivo (sin adivinar). 73 documentos con padre en el corpus.
- [x] 1.8 **Bug encontrado al implementar**: atribuir el preámbulo y un bloque
      a la misma transacción numerando cada uno desde 1 producía **952
      `chunk_id` duplicados en 223 archivos**, violando la unicidad que la spec
      exige. Corregido acumulando por `document_id` con un contador por slug
      compartido. Verificado: 0 duplicados en el corpus completo, con test que
      lo fija.

## 2. Documentos índice/capítulo

- [x] 2.1 Clasificar como índice cuando el documento no tiene ninguna sección
      de tabla pura Y tiene densidad alta de enlaces a otros documentos.
      Umbrales calibrados contra el corpus y expuestos como settings
      (`INDEX_DOC_MIN_LINKS=5`, `INDEX_DOC_MIN_LINK_DENSITY=3.0` enlaces por
      100 palabras) porque son elegidos, no derivados — ver `design.md` §7d.
- [x] 2.2 `document_kind` (`content` / `index`) agregado a `ChunkedDocument` y
      a `ChunkMetadata`, más `child_links` con los códigos de los hijos.
- [x] 2.3 **Contradicción resuelta hacia marcar, no descartar.** Esta tarea
      decía "no trocear un índice como contenido", pero `design.md` §2 ya
      argumentaba marcarlo y dejar decidir al retrieval. Se resolvió a favor de
      marcar: los dos errores no son simétricos — marcar un índice real como
      contenido solo deja chunks de bajo valor, mientras marcar contenido real
      como índice sacaría reglas de negocio del camino en silencio, violando la
      regla no negociable del repo. Los enlaces quedan en `child_links`.
- [x] 2.4 Test con `policies/ca001a.md` como fixture: se clasifica `index`,
      expone `CA047` entre sus hijos, y sus chunks se producen marcados.
- [x] 2.5 Verificado sobre el corpus: 37 documentos índice (1,6%), con 490
      chunks (0,7%). Se revisó a mano la lista completa de capturados y los
      casi-capturados (densidad 1,0-3,0), que quedan como contenido.

## 2bis. Verificación del umbral (hallazgo)

- [x] 2bis.1 El nombre de archivo `*_index` / `*_intro` **no** sirve como verdad
      de referencia para calibrar: de esos 46 archivos, la mediana de densidad
      de enlaces es 0,82 y el percentil 25 es 0,00 — muchos son prosa
      conceptual sin enlaces. La regla estructural, en cambio, captura los
      índices reales (`ca001a`, `dp003_a`, `si001_a`, los `*_index` de módulo).

## 3. Breadcrumb desde `WINDOWS` — DESBLOQUEADO

El usuario aportó el export (`Life_Windows.xls`, tabla completa: 3390 filas ×
23 columnas) el 2026-08-31. El MCP de DiWork no sirvió para exportarlo —
Oracle inalcanzable (`NJS-530`, host no resoluble) y Azure Blob con cadena TLS
rota; ambos son de conectividad del servidor MCP, no de la consulta.

- [x] 3.1 Export convertido a `data/windows_tree.csv` (3389 filas: código,
      padre, descripción) y su ruta en `app/config.py`
      (`WINDOWS_TREE_PATH`). La conversión es reproducible con
      `scripts/import_windows_tree.py`; `xlrd` se usa de forma **transitoria**
      (`uv run --with xlrd`), no como dependencia del proyecto, porque se
      necesita una vez por export y no en runtime. Verificado: el script
      reproduce el CSV byte por byte.
- [x] 3.2 `app/generation/rag/navigation.py` carga el árbol y resuelve el
      camino hasta `MENU` con **profundidad variable**. Los dos casos del
      documento de dominio validan exactos: `CA001` → `MENU > DMECAR > CA001`
      (sin submódulo) y `CAC020` → `MENU > DMECAR > DMECCA > CAC020`.
      **La profundidad real llega a 6 niveles**, no 2-3: el submódulo es el
      primer nivel bajo el módulo y el camino completo se guarda en
      `navigation_path` para no perder los intermedios más profundos.
- [x] 3.3 Distinción estructural nodo/hoja: un código que aparece como
      `SCODMEN` de otra fila es nodo. 194 nodos, 3195 hojas. Verificado contra
      los 6 códigos que cita el documento de dominio (`MCONTA`, `MERCP`,
      `MCAJBA`, `MGENER` nodos; `MEGAA`, `MCO511` hojas): **6/6 coinciden**.
- [x] 3.4 `module_code`/`module_name`/`submodule_code`/`submodule_name` en
      `ChunkMetadata`, más `navigation_path` e `is_menu_node` en
      `ChunkedDocument`. Todos opcionales: ausente se lee como ausente.
- [x] 3.5 Tests de los dos casos documentados, más profundidad 5, más los 6
      códigos nodo/hoja, más los casos que el export NO cubre.
- [x] 3.6 **La regla estructural pisa el patrón de código, y encontró un
      contraejemplo real.** Mi inferencia del grupo 4 ("`M`+dígitos = hoja")
      era 941/942 correcta: `MA6835` es un nodo de menú indistinguible por
      patrón de las 941 hojas de mantenimiento. Con el árbol cargado se
      clasifica `menu_node`. Se agregó ese tipo.
- [x] 3.7 El árbol es **opcional**: sin el export el pipeline corre igual y no
      resuelve breadcrumb, con test que lo fija. El export es una foto parcial
      de una instalación, no una precondición para trocear.
- [x] 3.8 **Bug encontrado al medir**: `scripts/chunk_corpus.py` construía
      `FunctionalSpecChunker()` directo en vez de pasar por la raíz de
      composición, así que la corrida batch nunca recibía el árbol — 0% de
      breadcrumb resuelto, en silencio, mientras el test directo funcionaba.
      Ahora usa `get_functional_spec_chunker()`, así el batch y la API HTTP
      comparten una única configuración.

## 4. Clasificación de tipo de transacción

- [x] 4.1 `app/generation/rag/taxonomy.py` con la tabla de `(regex, tipo)` como
      **datos** recorridos en orden, no como ramas de código. Cada regla lleva
      anotado cuántos `document_id` distintos matchea hoy, para que una edición
      futura pueda ver si movió más de lo que quería.
- [x] 4.2 Tipos implementados: `interface`, `key_request`, `process_report`,
      `query`, `maintenance`, `functional_abm`, `unknown`.
      **Desviación:** se agregó `key_request` (sufijo `_k`/`_K`, más el único
      caso de `k` pegado, `CA001k`), que no estaba en la lista propuesta. Son
      113 documentos y es la forma dominante de los archivos multi-transacción;
      llamarlos `functional_abm` habría borrado la distinción justo donde hay
      evidencia dura. El tipo de su familia queda alcanzable por
      `parent_transaction_code`.
- [x] 4.3 `unknown` explícito con razón cuando ninguna regla matchea (416
      documentos: son ids de fallback por nombre de archivo, como
      `ACCOUNTING_INDEX` o `AU_C_RC`, que no son códigos de transacción).
      **Revisión respecto de lo propuesto:** los `M...` con dígitos SÍ se
      clasifican `maintenance` en vez de `unknown` — ver `design.md` §7e.
- [x] 4.4 El separador del nombre de archivo no se usa como señal de nada: el
      código sale del contenido (grupo 1). `accounting_cpl500` resuelve a
      `CPL500`.
- [x] 4.5 `transaction_type` agregado a `ChunkMetadata` y estampado en cada
      chunk; `transaction_type_reason` en `ChunkedDocument` solo cuando es
      `unknown`.
- [x] 4.6 Tests por tipo con 18 códigos reales del corpus, más casos `unknown`,
      más un test del orden de precedencia de las reglas.
- [x] 4.7 Distribución medida sobre el corpus: `maintenance` 669 (29,7%),
      `unknown` 416 (18,5%), `process_report` 393 (17,5%),
      `functional_abm` 374 (16,6%), `query` 176 (7,8%), `key_request` 113
      (5,0%), `interface` 107 (4,8%). 81,5% clasificado.

## 5. Cierre

- [x] 5.1 `data/chunks/` regenerado: 2169 archivos → **2250 documentos**
      (antes 2169 entradas) → 66.618 chunks (antes 67.121). La diferencia de
      −503 chunks está explicada en `design.md` §7b: eran chunks cuyo contenido
      era solo el código de transacción repetido.
- [x] 5.2 `uv run pytest` (111 tests), `uv run ruff check .` y
      `uv run python scripts/validate_specs.py` en verde.
- [x] 5.3 Deltas integrados en `openspec/specs/` y cambio archivado.

## 6. Cobertura final medida

- [x] 6.1 **Breadcrumb**: 1220 documentos (54,2%) resuelven camino hasta
      `MENU`, cubriendo 39.594 chunks (59,4%); 1187 de ellos con submódulo.
      El 45,8% restante no es un fallo del código sino el alcance del export:
      690 de nuestros ids no están en el árbol (muchos son ids de fallback por
      nombre, que no son códigos de transacción) y 324 están en el árbol bajo un
      padre que no llega a la raíz.
- [x] 6.2 **Tipo de transacción**: `maintenance` 669 (29,7%), `unknown` 415
      (18,4%), `process_report` 393 (17,5%), `functional_abm` 374 (16,6%),
      `query` 177 (7,9%), `key_request` 113 (5,0%), `interface` 107 (4,8%),
      `menu_node` 2 (0,1%).
- [x] 6.3 **Módulos resueltos** (top): Mantenimiento 568, Cobranzas 144,
      Pólizas 133, Intermediarios 80, Siniestros 64, Interfaces 54, Caja y
      Bancos 41, Co/Reaseguros 36.

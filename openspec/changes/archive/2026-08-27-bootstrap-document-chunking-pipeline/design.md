# Diseño

Las decisiones no obvias de este cambio, y qué se descartó. Varias salieron de
mirar los documentos reales, no de diseñar en abstracto.

---

## 1. La estrategia de chunking se decide por forma, no por nombre de sección

**Primera versión:** una lista fija de cinco secciones canónicas (`Función`,
`Efecto`, `Notas para el programador`, `Campos`, `Validaciones`), con
`Campos`/`Validaciones` cableadas como "tabla" y el resto como "narrativa".
Funcionó perfecto contra los tres documentos de `policies` con los que se
validó.

**Por qué se cambió:** al escanear el corpus completo (2171 archivos, 30
módulos) resultó que solo **717** documentos tienen esas cinco secciones.
Otros módulos usan `Función general`, `Proceso`, `Parámetros de entrada`,
`Información técnica`, `Acciones de menú`; algunos no tienen ningún H2. Con la
lista fija, esos ~1450 documentos habrían producido **cero chunks en silencio**
— exactamente el modo de falla que el proyecto no puede permitirse.

**Decisión:** descubrir cualquier H2 y decidir la estrategia por la forma del
cuerpo (¿es una tabla pura? → fila por chunk; si no → narrativa). Un documento
sin H2 se trocea como una sección implícita `Introducción`.

**Efecto medido:** los cuatro formatos que antes daban cero chunks pasaron a
trocear correctamente; la corrida completa dejó solo 2 archivos en cero, ambos
por fuente corrupta.

**Descartado:** mantener la lista fija y agregarle sinónimos. Con headings tan
abiertos en 30 módulos, un diccionario de sinónimos falla en silencio con cada
heading nuevo — el mismo problema, más tarde.

## 2. El slug del `chunk_id` se genera, no se traduce a mano

La primera versión tenía un diccionario `{"Función": "function", "Campos":
"fields", ...}`. Al abrir la detección a cualquier heading, ese diccionario se
volvió un `KeyError` esperando a pasar. Se reemplazó por un slug derivado del
propio texto en español (ASCII, minúscula, guiones bajos).

Como dos secciones de un documento pueden compartir heading, la numeración
lleva un contador **por slug** en vez de reiniciar en 1 por sección; si no, dos
bloques `Efecto` producirían `chunk_id` duplicados.

## 3. El presupuesto de tokens se calcula por nodo, no una vez arriba

**Bug real encontrado por los tests.** El techo de 500 tokens se validaba
contra el texto de la unidad más un `header_tokens` estimado **una sola vez**
al tope de la sección. Pero el contextual header incluye el `bullet_path`, que
crece a medida que el chunking desciende niveles. En CA014 eso dejó pasar tres
chunks de 505, 512 y 527 tokens.

**Decisión:** cada unidad calcula el presupuesto desde SU PROPIO header, con su
breadcrumb actual. El test `test_no_narrative_chunk_exceeds_the_token_cap` fija
esto contra los tres documentos reales.

## 4. Dos formas de tabla rota, no una

El defecto de exportación descrito al inicio del trabajo era una sola forma:
dos `####` seguidos de filas `etiqueta | valor` (CA014 "Ramos generales",
CA001 "Tipo de registro").

Al implementarlo apareció una **segunda forma** no descrita: en CA001 "Tipo de
inicio de vigencia / Fecha a mostrar", cada fila también quedó partida — su
etiqueta como su propio `####` y su valor como una línea `| valor` sin celda
izquierda. Ambas están implementadas y cada una tiene su test con el fixture
real.

**Falso positivo evitado:** `####` también se usa para subtítulos legítimos.
La reparación solo dispara cuando la corrida de headers está inmediatamente
seguida de líneas con `|`; hay un test negativo que fija que un heading real
seguido de prosa queda intacto.

## 5. Celda faltante: rellenar y advertir, nunca descartar

Una fila puede traer menos celdas que columnas. Descartar la fila, o la celda,
perdería una regla de negocio de seguros sin dejar rastro. Se rellena con `""`,
se emite `logger.warning` y la advertencia queda además en el registro
`RepairedTable` devuelto, junto con el bloque original crudo.

## 6. `metadata` y `stats` como modelos, no `dict`

Con `metadata: dict`, Swagger no tiene propiedades que declarar: la pestaña
Schema muestra un `object` vacío y Example Value un placeholder
`additionalProp1`. Agregar `examples=[...]` arregla solo Example Value, no
Schema. Se reemplazó por `ChunkMetadata` e `IngestStats` (modelos anidados),
y ahí Swagger declara los atributos reales en ambas pestañas.

## 7. Las capas del curso que NO se replicaron

`app/ingestion/` del curso es un pipeline batch dirigido por catálogo YAML, con
jobs en background y tracking en Postgres, para otro tipo de fuente. Nuestra
ingesta es síncrona, sin persistencia y sin catálogo. `app/foundation/` es
wrapper de LLM, guardrails y persistencia — nada de eso existe todavía acá.

**Decisión:** no pre-construir capas vacías por simetría con el curso. Cuando
entre embeddings el lugar es `app/generation/rag/embedding/`; cuando entre
pgvector, `app/foundation/persistence/`.

Por la misma razón, `chunking/base.py` existe pero sin la clase abstracta
`Chunker` del curso: acá hay una sola estrategia, y una abstracción con una
única implementación es ruido. Entra cuando entre la segunda.

## 8. Los nombres de sección quedan en español

Todo el código va en inglés, pero los valores de `metadata.section`
(`"Función"`, `"Efecto"`, ...) se conservan en español. Son el heading literal
del documento fuente: son datos, no identificadores, y traducirlos rompería la
trazabilidad del chunk hacia el texto real.

## 9. Los dos archivos en cero chunks no se "arreglaron"

La corrida completa dejó dos archivos sin chunks: `collections/col1025.md`
está vacío (0 bytes) y `maintenance/mbc501.md` no es markdown — es un export
HTML de Word en UTF-16 con extensión `.md`.

**Decisión:** no agregar código para tolerarlos. Son defectos de la fuente;
quedan listados en el reporte para que una persona los re-exporte. Un
`try/except` que los trague convertiría un problema de datos visible en uno
invisible.

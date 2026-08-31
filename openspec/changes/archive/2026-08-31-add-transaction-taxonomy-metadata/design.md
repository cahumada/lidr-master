# Diseño

## 1. Cómo segmentar un archivo multi-transacción

El corpus marca cada transacción dentro de un archivo con un bloque H1 seguido
de su bloque de id (`` `**(BC005_k)**` ``), y separa bloques con headings
placeholder `## .`.

**Enfoque elegido (corregido durante la implementación): segmentar por la línea
de id.** Cada línea de id se extiende hacia atrás hasta el H1 más cercano que la
precede —su título— sin cruzar la línea de id anterior.

**Descartado — segmentar por `# ` (H1), que era el plan original:** al
implementarlo resultó que H1 **no es un delimitador confiable**. El export emite
`# ` también para líneas de continuación de bullets; en
`accounting/cp002.md` hay ocho de esas (`# · _Adicionalmente..._`,
`# o _Caso contrario:_`, `# § _Se construye..._`) entre el H1 real y el bloque
de la transacción. Partir por H1 habría inventado ocho bloques espurios en ese
solo archivo. La línea de id, en cambio, es exactamente la marca de "acá
empieza una transacción". Hay un test que fija este caso.

**Descartado — segmentar por `## .`:** los delimitadores placeholder son la
señal más visible, pero son un artefacto de la exportación y no aparecen en
todos los archivos multi-transacción.

**Descartado — un chunk por transacción con todo su contenido:** rompería el
techo de tokens. La segmentación es solo para *atribuir*; el chunking dentro de
cada bloque sigue igual.

**Caso borde a resolver en implementación:** el bloque H1 contenedor de
`bc005.md` (`Función general` + `Información técnica` + `Páginas asociadas`) no
tiene bloque de id propio: describe el conjunto, no una transacción. Su
contenido no debe atribuirse a ninguna de las dos transacciones hijas. La regla
propuesta: un bloque sin id propio, en un archivo donde otros bloques sí tienen
id, es contenedor — se atribuye al código del archivo (fallback) y se marca
como tal, no se reparte entre los hijos.

## 2. Cómo detectar un documento índice/capítulo

Señales disponibles en `ca001a.md`: muchos enlaces a hijos (31 `.html`),
ausencia de `Campos`/`Validaciones`, y volumen bajo (52 líneas).

**Enfoque elegido:** clasificar como índice cuando el documento **no tiene
ninguna sección de tabla pura** Y tiene una densidad alta de enlaces a otros
documentos. Ambas condiciones juntas: cada una por separado da falsos
positivos (hay documentos de contenido cortos sin tablas, y documentos de
contenido con muchos enlaces).

**Descartado — clasificar por el sufijo del nombre (`a` en `ca001a`)**: el
sufijo alfabético también aparece en transacciones reales (`ca014a`, `ca013a`),
así que no discrimina. Es exactamente el error que el documento de dominio
advierte: adivinar por convención de nombre en vez de mirar la estructura.

**Qué se hace con un índice:** no se descarta. Se marca
(`document_kind='index'`) y sus enlaces quedan como relaciones padre-hijo
cruzables contra `WINDOWS`. Descartarlo perdería la única evidencia de
jerarquía que hay en los `.md`; trocearlo como contenido mete ruido en el
retrieval. Marcarlo permite decidir en la capa de retrieval, que es donde
corresponde.

## 3. Clasificación por patrón de código: regla, no adivinanza

La convención de la sección 4 del documento de dominio es `[TÁCITO]` — no está
en ninguna tabla. Eso obliga a dos cosas:

1. **Codificarla como datos, no como ramas de código.** Una tabla de
   `(regex, tipo)` recorrida en orden es auditable y editable cuando aparezca
   un contraejemplo; un `if/elif` de seis ramas no.
2. **Devolver `unknown` explícito**, nunca un tipo por defecto. Si un código no
   matchea ninguna regla, el motor debe decirlo. Un tipo inventado por defecto
   es peor que ningún tipo: se propaga como si fuera un hecho.

**Orden de precedencia importa:** `INT\d+` antes que la regla genérica, y la
regla de `M...` **solo** aplica sobre un código ya confirmado como hoja. Sin
datos de `WINDOWS`, un `M...` no se puede clasificar como mantenimiento con
confianza — se devuelve `unknown` con la razón, no `maintenance` a la ligera.
Medido: 669 de 2169 archivos matchean `^M[A-Z]{1,3}\d+`, y por la sección 3 una
parte de esos son carpetas de menú. Clasificarlos todos como mantenimiento
sería inventar 669 hechos.

## 4. Por qué el breadcrumb va como campos planos y no como un árbol

`ChunkMetadata` es el contrato que llega al vector store, y ahí se filtra por
igualdad, no por recorrido de árbol. Un breadcrumb anidado obligaría a
aplanarlo en cada consulta.

**Enfoque elegido:** campos planos (`module_code`, `module_name`,
`submodule_code`, `submodule_name`, `transaction_type`) más el camino completo
como texto para trazabilidad. `submodule_*` queda `None` cuando el árbol tiene
solo 2 niveles — que es el caso de `CA001`, así que no es un caso borde raro
sino la mitad de los ejemplos conocidos.

**Consecuencia de la profundidad variable:** nada en el código puede asumir
que existe un submódulo. El campo es opcional por diseño, no por prolijidad.

## 7. Hallazgos de la implementación (grupos 0 y 1)

### 7a. El contenedor que coincide con un bloque debe fusionarse, no coexistir

El plan trataba el preámbulo como un documento contenedor siempre. Medido: en
728 archivos el código del contenedor coincide con el de un bloque declarado, y
mantenerlos separados producía **dos entradas con el mismo `document_id`** y,
peor, **952 `chunk_id` duplicados en 223 archivos** (cada uno numeraba sus
secciones desde 1).

**Decisión:** acumular el contenido **por `document_id`**, con un contador por
slug compartido. Si el preámbulo resuelve al mismo código que un bloque, es la
introducción de esa transacción y se fusiona; solo queda como contenedor
marcado cuando no coincide con ninguno — 4 casos en todo el corpus.

### 7b. −503 chunks, y por qué es una mejora

La corrida completa pasó de 67.121 a 66.618 chunks. La diferencia está
explicada, no es pérdida de información: al reconocer más formas de línea de id,
esas líneas se descartan de la sección `Introducción` en vez de quedar como
chunk. El caso verificado, `maintenance/ma0192.md`, tenía un chunk cuyo
contenido completo era `` \(`MA00192`\) `` — el código repetido, cero valor para
retrieval. La distribución por módulo de las líneas de id recién reconocidas
(maintenance 505, collections 100, claims 80, ...) coincide con la distribución
del delta de chunks (maintenance −300, collections −15, claims −24, ...).

Nótese la forma nueva encontrada acá: `` \(`CODE`\) `` —paréntesis escapados
afuera, backticks adentro— que el patrón viejo no podía matchear porque exigía
un backtick al inicio.

### 7c. Tres discrepancias de la FUENTE, no del pipeline

Al tomar el contenido como autoritativo aparecieron tres documentos cuyo código
declarado no coincide con su nombre de archivo:

| Archivo | Declara | Nota |
|---|---|---|
| `life/reports/vil900.md` | `VI701` | nombre y código declarado no se parecen |
| `maintenance/ma0192.md` | `MA00192` | un cero de más; probable typo de la fuente |
| `maintenance/st004.md` | `ST004_k` | solo declara la solicitud de clave, no `ST004` |

El pipeline hace lo correcto (el contenido manda) y quedan registrados acá para
revisión humana. No se agregó código para "corregirlos": inventar el código que
creemos que deberían tener sería fabricar un dato.

### 7d. El umbral de índice: calibrado, conservador y asimétrico a propósito

Intenté calibrar contra los nombres `*_index` / `*_intro` como verdad de
referencia. **No sirven:** de esos 46 archivos la mediana de densidad de enlaces
es 0,82 y el percentil 25 es 0,00 — muchos son prosa conceptual sin un solo
enlace. Usar el nombre habría sido justamente el error que la nota de dominio
advierte.

La regla estructural sí funciona. Con "sin tabla pura + ≥5 enlaces + ≥3,0
enlaces por 100 palabras" captura 37 documentos, y la lista completa revisada a
mano son los índices reales: los `*_index` de módulo con densidad 11-21, y los
documentos `_a` / `-a` de "Páginas asociadas" (`ca001a` 13,4; `dp003_a` 16,7;
`si001_a` 14,7; `os590_a` 12,7).

**Por qué conservador:** los umbrales dejan afuera cuatro índices de módulo
genuinos con mucha prosa (`cash_and_banks_index` 1,9; `producers_index` 1,8;
`designer_index` 1,5). Es deliberado: los dos errores no son simétricos. Dejar
un índice como contenido cuesta unos chunks de bajo valor; marcar contenido
como índice esconde reglas de negocio. Los umbrales son settings, no
constantes, porque son elegidos y no derivados — quien los mueva debería volver
a revisar la lista capturada.

**Y por eso se marca en vez de descartar** (§2 de este documento, contra lo que
decía la tarea 2.3): con marcado, un falso positivo del clasificador no borra
nada. Los 37 índices aportan 490 chunks, 0,7% del corpus.

### 7e. `M...` con dígitos sí es mantenimiento: la ambigüedad no aplica

El plan decía devolver `unknown` para todo `M...` sin datos de `WINDOWS`, porque
la nota de dominio advierte que puede ser hoja o carpeta. Medir el corpus lo
refinó:

- Las carpetas que la nota cita (`MCONTA`, `MERCP`, `MCAJBA`, `MGENER`) **no
  llevan dígitos**.
- Ningún código `M` sin dígitos tiene documento de especificación funcional.
  `MENU` es el único que aparece, y no matchea la regla (queda `unknown`).
- Los 669 códigos `M<letras><dígitos>` vienen de documentos que describen una
  transacción, y eso ya es evidencia de hoja: una carpeta de menú no tiene
  documento con Función/Campos/Validaciones.

Responder `unknown` para 669 documentos (30% del corpus) por una ambigüedad que
los datos no muestran sería falsa cautela: haría inservible el campo justo en el
módulo más grande. La confirmación por `WINDOWS` sigue siendo la autoritativa y
es el grupo 3.

### 7f. El árbol `WINDOWS` real: más irregular que los dos ejemplos

El export (3389 códigos) valida exacto los dos casos del documento de dominio,
y también los 6 códigos `M` que cita como nodos/hojas: 6 de 6 coinciden. Pero
el árbol completo es bastante más irregular de lo que sugerían esos ejemplos:

| Hecho | Consecuencia en el código |
|---|---|
| Profundidad de 1 a 6 niveles, no 2-3 | El submódulo es el *primer* nivel bajo el módulo; el camino completo se guarda en `navigation_path` para no perder los intermedios más profundos |
| 717 códigos sin padre (son su propia raíz) y 44 padres referenciados que no existen como fila | 794 códigos no llegan a `MENU`: se devuelve breadcrumb sin resolver, no un ancestro cualquiera llamado "módulo" |
| 2 ciclos | El recorrido lleva guarda de visitados; sin eso colgaba la corrida batch entera |

**Cobertura real: 54,2% de nuestros documentos** resuelven breadcrumb. Es el
alcance del export, no un fallo: 690 de nuestros ids no están en el árbol (en
buena parte son ids de fallback por nombre, que no son códigos de transacción) y
324 están en el árbol pero bajo un padre que no lleva a la raíz.

**Decisión:** el árbol es **opcional**. Sin el export el pipeline corre igual y
no resuelve breadcrumb. El export es una foto parcial de una instalación
(`Life_Windows`), no una precondición para trocear — atarle el chunking habría
hecho que el pipeline dependiera de un archivo que puede no estar.

### 7g. `MA6835`: la regla estructural encontró el contraejemplo

En §7e clasifiqué `M<letras><dígitos>` como `maintenance` por inferencia, sin
poder verificarla. Con el árbol se pudo: la inferencia era **941 de 942**
correcta, y el contraejemplo es `MA6835`, un nodo de menú indistinguible por
patrón de las 941 hojas.

Justo lo que la nota de dominio advertía: la regla estructural es preferible a
adivinar por la forma del código. Ahora, cuando el árbol está disponible,
`is_menu_node` **pisa** los patrones y `MA6835` se clasifica `menu_node` (tipo
agregado). Cuando no está, los patrones deciden solos — con esa precisión
medida de 941/942, que ahora está documentada en vez de ser una esperanza.

### 7h. El bug que solo aparece midiendo, no testeando

Con el árbol cargado y los tests en verde, la corrida batch daba **0% de
breadcrumb resuelto**. `scripts/chunk_corpus.py` construía
`FunctionalSpecChunker()` directo en vez de pasar por
`get_functional_spec_chunker()`, así que nunca recibía el árbol ni ninguna
otra configuración.

Los tests no lo veían porque instancian el chunker con sus propios argumentos.
La lección concreta: **un script que se saltea la raíz de composición es una
segunda configuración silenciosa**. Ahora el batch y la API comparten una sola.

## 5. Riesgo asumido: el corpus ya troceado queda obsoleto

`data/chunks/` (67.121 chunks) se generó con la atribución vieja. Al
implementar esto hay que regenerarlo, y los `chunk_id` de los archivos
multi-transacción van a cambiar (el slug de sección se mantiene, pero el
`document_id` que lo prefija, no).

No hay persistencia todavía, así que regenerar es barato: 14 segundos. Este
riesgo sería serio recién cuando haya embeddings pagados sobre esos chunks —
razón de más para arreglar la atribución **antes** de la capa de embeddings, no
después.

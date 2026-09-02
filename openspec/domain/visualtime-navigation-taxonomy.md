# Dominio: taxonomía de navegación de VisualTIME

Reference knowledge about the SOURCE system (VisualTIME), not about this
service. Nothing here is a requirement on our code — see
`openspec/specs/` for that, and
`openspec/changes/add-transaction-taxonomy-metadata/` for the work this
knowledge motivates.

|| Conocimiento de referencia sobre el sistema FUENTE (VisualTIME), no sobre
este servicio. Nada de acá es un requerimiento sobre nuestro código — para
eso está `openspec/specs/`, y en
`openspec/changes/add-transaction-taxonomy-metadata/` el trabajo que este
conocimiento motiva.

**Aportado por:** el usuario (analista funcional del sistema), 2026-08-31.

## Estado de la evidencia || Evidence status

Cada afirmación lleva su estado. No colapsar una hipótesis en un hecho: la
diferencia decide si el motor puede confiar en la regla o debe verificarla.

- `[VALIDADO-BD]` — el usuario lo validó con consultas sobre la base real.
- `[TÁCITO]` — conocimiento tácito del usuario, no documentado en ninguna
  tabla ni archivo. No es verificable automáticamente; se toma como
  autoritativo pero es la clase de regla que conviene revisar si aparece un
  contraejemplo.
- `[HIPÓTESIS]` — planteado explícitamente como hipótesis inicial, pendiente
  de validar.
- `[VERIFICADO-CORPUS]` — verificado en esta sesión contra los `.md` reales;
  se indica cómo.

---

## 1. El árbol de menú vive en la tabla `WINDOWS` `[VALIDADO-BD]`

La taxonomía completa (Módulo → Submódulo → Transacción) es **100% derivable
de la base, sin trabajo manual**. La tabla `WINDOWS` contiene el árbol de menú
completo, con estructura recursiva auto-referenciada:

| Campo | Significado |
|---|---|
| `SCODISPL` | código de la ventana/transacción/nodo |
| `SCODMEN` | código del nodo padre (mismo campo, referencia a sí misma) |
| `SDESCRIPT` | descripción del nodo |

Consulta tipo, para obtener el camino de un código hasta la raíz:

```sql
SELECT LEVEL AS NIVEL, TRIM(SCODISPL) AS SCODISPL, TRIM(SCODMEN) AS SCODMEN, TRIM(SDESCRIPT) AS SDESCRIPT
FROM WINDOWS
START WITH TRIM(SCODISPL) = '<CODIGO>'
CONNECT BY PRIOR TRIM(SCODMEN) = TRIM(SCODISPL)
ORDER BY LEVEL DESC
```

El nodo raíz es `MENU`. `[VERIFICADO-CORPUS]` — corroborado indirectamente:
`general/general_menu.md` documenta la transacción `` `MENU` `` y dice que "la
estructura del menú depende de la estructura registrada en el archivo de
transacciones", consistente con que el árbol viva en la base y no en los `.md`.

## 2. La profundidad del árbol es variable `[VALIDADO-BD]`

Confirmado con ejemplos reales:

- `CA001` → 2 niveles: `MENU` → `DMECAR` ("Pólizas", Módulo) → `CA001`
  (Transacción). **Sin submódulo intermedio.**
- `CAC020` → 3 niveles: `MENU` → `DMECAR` ("Pólizas", Módulo) → `DMECCA`
  ("Consultas de Pólizas", Submódulo) → `CAC020` (Transacción).

**Implicancia:** el motor debe soportar profundidad variable. No asumir una
jerarquía fija de 3-4 niveles, ni que "el penúltimo nivel es siempre el
submódulo".

## 3. Nodo de navegación vs. transacción ejecutable `[VALIDADO-BD]`

Regla **estructural**, validada contra datos reales:

- Un nodo **con hijos** (aparece como `SCODMEN` de otras filas) es un nodo de
  menú/carpeta.
- Un nodo **hoja** (nadie lo tiene como padre) es una transacción ejecutable real.

Se probó sobre 11 códigos que empiezan con `M` (los candidatos ambiguos): 9
resultaron nodos con hijos — menús/carpetas tipo "Tablas de...", "Reportes
de..." (`MCONTA`, `MERCP`, `MCAJBA`, `MGENER`, ...) — y 2 resultaron hojas
(`MEGAA`, `MCO511`), transacciones reales de mantenimiento.

**Por qué esta regla y no el patrón del código:** es estructural y universal,
no depende de adivinar convenciones de nomenclatura. Preferirla siempre que
haya datos de `WINDOWS` disponibles.

**Actualización:** el export trae `NWINDOWTY`, y el tipo 8 **declara** que un
código es un menú. Eso es mejor que esta regla estructural, que acierta 192 de
205 y falla en 19. La heurística de hijos queda como respaldo para los códigos
sin tipo declarado. Ver
[visualtime-window-types.md](visualtime-window-types.md).

## 4. Clasificación de tipos de transacción `[TÁCITO]`

Convención de nomenclatura confirmada por el usuario. **No está documentada en
ninguna tabla**, así que no es verificable automáticamente: se aplica sobre un
código ya identificado como hoja (sección 3).

| Patrón del código | Tipo | Descripción |
|---|---|---|
| `[Módulo]L[código]` (`CAL...`, `COL...`, `AGL...`) | **Proceso/Reporte** | Genera un reporte o ejecuta un proceso grande de BD alterando entidades; puede mostrar reporte al final. El programador tiene libertad de diseño. |
| `[Módulo]C[código]` (`CAC...`, `COC...`, `AGC...`) | **Consulta** | Solo consulta datos; no actualiza BD, no genera reportes en su gran mayoría. |
| `[Módulo][código]` sin `L` ni `C` (`CA001`, `CO001`) | **Funcional / ABM** | Ejecuta una o varias funcionalidades; altera las entidades sobre las que actúa. |
| `INT[código]` | **Interfaz** | Desarrollada desde el módulo de Interfaces, que actúa como motor generador con reglas y estructura fijas de ejecución (a diferencia de las `L`, donde el programador decide libremente). Puede ser de entrada o de salida del sistema. |
| `M[Módulo][código]` **que resulta hoja** | **Mantenimiento** | Permite parametrizar datos maestros que luego consumen el resto de las transacciones. Los `M...` que resultan nodos con hijos son carpetas de menú, no mantenimientos (sección 3). |

### Códigos con guion o guion bajo `[TÁCITO]`

`CA13-1`, `BC005_K`, `VI7501_A`: **en su gran mayoría** son sub-páginas o
pestañas de una transacción padre (`CA13-1` cuelga de `CA13`), no
transacciones independientes con entrada propia en el árbol de menú.

Nótese el "en su gran mayoría": la regla admite excepciones, así que no es
segura para decidir por sí sola.

## 5. Estructura de los `.md`: la relación archivo ↔ transacción no es 1:1 `[VERIFICADO-CORPUS]`

Revisados ~19 archivos de ejemplo por el usuario; los tres casos verificados
independientemente en esta sesión:

**a. 1 archivo = 1 transacción** (caso simple): `designer/dp003.md` → `DP003`.

**b. 1 archivo = varias transacciones**: `clients/bc005.md` contiene `BC005_k`
y `BC005`. Estructura real verificada:

```
# Cambio y Unificación del Código del cliente     <- H1 del contenedor
## Función general
## Información técnica
#### Páginas asociadas
BC005\_k |  Solicitud de código a actualizar      <- tabla rota: lista los hijos
BC005 |  Cambio y Unificación de Cliente
## .                                              <- delimitador
## .
# Solicitud de código a actualizar                <- H1 de la 1a transacción
`**(BC005_k)**`
## Función / ## Campos / ## Validaciones
## .
## .
# Cambio y Unificación del Código del cliente     <- H1 de la 2a transacción
`**(BC005)**`
## Función / ## Efecto / ## Notas... / ## Campos / ## Validaciones
```

Es decir: **varios bloques H1, cada uno con su propio bloque de id y su propio
juego de secciones**, separados por headings placeholder `## .`.

**c. 1 archivo = nodo "capítulo"/índice**: `policies/ca001a.md` describe el
nodo padre y solo enlaza a sus hijos (31 enlaces `.html` a `ca047`, `ca025`,
...), sin `Campos` ni `Validaciones` propios. Es metadata de agrupación, no
contenido de una transacción hoja. Aporta, eso sí, relaciones padre-hijo
cruzables contra `WINDOWS`.

**Implicancia:** el motor debe determinar de qué transacción(es) habla un
archivo **parseando su contenido** (el código aparece en el texto, ej.
`` `**(BC005_k)**` ``), no confiando en el nombre del archivo. Y debe
distinguir "documento de contenido" de "documento índice/capítulo".

## 6. La estructura de secciones varía según el tipo de transacción `[VERIFICADO-CORPUS]`

| Tipo | Secciones observadas | Ejemplos |
|---|---|---|
| Funcional/ABM | Función → Efecto → Notas al Programador → Campos (tabla) → Validaciones (tabla) | `dp003.md`, `dp044.md`, `bc005.md` |
| Mantenimiento | Función → Valores posibles (lista código/descripción de tabla de valores fijos). **Sin** Campos/Validaciones tradicionales | `ma0087.md`, `ma0140.md` |
| Interfaz | Función general → Información técnica → Características de la interfaz → Parámetros de entrada → Tablas → Campos → Validaciones → Proceso → Nota para el programador | `int54552.md`, `int54584.md` |
| Proceso/Reporte (`L`) | Función general → Información técnica → Parámetros → Frecuencia de ejecución → Requisitos → Instrucciones de ejecución/interrupción → Proceso batch (Proceso, Efecto, Fórmulas, Listados) → Observaciones | `vil009.md`, `crl012.md` |
| Consulta | Función general → Acciones de menú → Información técnica → Notas para el programador → Campos (**sin** Validaciones, en general, por ser de solo lectura) | `crc001.md` |

Los 11 archivos citados existen en el corpus `[VERIFICADO-CORPUS]`.

**Implicancia:** la plantilla de parseo/generación puede y debe ser específica
por tipo de transacción, en vez de un prompt genérico único.

## 7. Fuente técnica en vivo a consultar por tipo `[HIPÓTESIS]`

Planteado explícitamente como hipótesis inicial, pendiente de validar:

| Tipo | Fuente técnica en vivo (hipótesis) | Costo relativo esperado |
|---|---|---|
| Funcional/ABM | `DescribeTable` + `ExplainTableRole` de las tablas mencionadas | Medio |
| Consulta | Similar a ABM pero más liviano (sin validaciones de escritura) | Bajo |
| Mantenimiento | Casi no requiere cruce técnico (tablas de valores fijos) | Muy bajo |
| Interfaz/Reporte | `SearchInSource` / `ExplainRoutine` de la rutina batch, si se logra identificar | Medio-alto |

---

## Verificaciones y caveats hallados en esta sesión

Resultados de contrastar lo anterior contra el corpus y contra el código actual.

### El defecto que esto destapa en el pipeline actual `[VERIFICADO-CORPUS]`

`FunctionalSpecChunker` hoy asume 1 archivo = 1 documento. Alcance medido
sobre los 2169 archivos / 67.121 chunks del corpus generado:

| Categoría | Archivos | Chunks |
|---|---|---|
| Con bloque de id en el contenido | 391 (18,0%) | — |
| Sin bloque de id — fallback al nombre es **correcto** | 1778 (82,0%) | — |
| **Multi-transacción** (≥2 códigos en un archivo) | **72 (3,3%)** | **3484 (5,2%)** |
| **Id mal asignado** (el real ≠ el asignado) | **43 (2,0%)** | **2143 (3,2%)** |
| **Índice/capítulo** troceado como contenido | **60 (2,8%)** | **2132 (3,2%)** |

Ejemplos concretos:

- `accounting/accounting_cpl500.md` → id real `CPL500`, asignado
  `ACCOUNTING_CPL500` (151 chunks). El nombre de archivo lleva el módulo como
  prefijo y contamina el id.
- `batch_processes/btc001_1.md` → ids reales `BTC001` + `BTC001_k`, asignado
  `BTC001_1`, que **no es un código de transacción real**: es un artefacto del
  nombre de archivo.
- `accounting/cp002.md` → `CP002` y `CP002_k` quedan ambos como `CP002`.
- `policies/ca001a.md` → 5 chunks tratados como contenido, cuando es índice
  (31 enlaces, sin Campos/Validaciones).

Los headings placeholder `## .` ya se descartan correctamente por
`_is_junk_heading`.

**Corrección de una lectura inicial engañosa:** una primera medición dio
"96,2% de los archivos resuelven el id por fallback al nombre". Ese número es
real pero no es un defecto: el 82% de los archivos **no tiene** bloque de id, y
ahí el fallback es el comportamiento correcto. El defecto son los 43 archivos
donde el id existe y se asigna otro.

### El patrón multi-transacción es sistemático, no aleatorio `[VERIFICADO-CORPUS]`

De los 72 archivos multi-transacción, la forma dominante es
`<CODIGO>` + `<CODIGO>_k`: `CP002`+`CP002_k`, `OP008`+`OP008_k`,
`SG001`+`SG001_K`, `BC005`+`BC005_k`. Es la transacción de solicitud de clave
acompañando a su transacción principal — el `unit_type` `transaction_key` del
brief de procesamiento, que enlaza al padre vía `parent_transaction_code`.

Esto hace la corrección tratable: no es un parseo libre de N transacciones
arbitrarias, es reconocer un par padre/solicitud-de-clave bien definido (más
tres casos con sufijo `_K` en mayúscula).

### El regex de id actual no ve varias formas reales `[VERIFICADO-CORPUS]`

`DOCUMENT_ID_PATTERN = \(([A-Z]{2,4}\d{3}[a-z]?)\)` falla contra códigos
que existen en el corpus:

| Código | ¿Matchea? | Por qué |
|---|---|---|
| `(CA014)`, `(CA001k)`, `(CPL500)` | sí | — |
| `(BC005_k)`, `(VI7501_A)` | **no** | el guion bajo no está en el patrón |
| `(MENU)` | **no** | exige `\d{3}`; `MENU` no tiene dígitos |
| `(CA13-1)` | **no** | solo 2 dígitos y guion |

Esta es la causa raíz de que los ids del sufijo `_k` se pierdan. Las formas de
bloque de id encontradas en el corpus son cuatro:
`` `**(CODE)**` `` (336), `` **`(CODE)`** `` (24), `` `(CODE)` `` (2), y una
malformada.

### El export de `WINDOWS` ya está disponible y valida esta nota `[VERIFICADO-CORPUS]`

El usuario aportó el export el 2026-08-31 (`Windows.xls`: 3390 filas × 23
columnas). Convertido a `data/windows_tree.csv` (3389 códigos) con
`scripts/import_windows_tree.py`. Contrastado contra esta nota:

| Afirmación de esta nota | Resultado |
|---|---|
| `CA001` → `MENU` → `DMECAR` ("Pólizas") → `CA001`, sin submódulo | **exacto** |
| `CAC020` → `MENU` → `DMECAR` → `DMECCA` ("Consultas de Pólizas") → `CAC020` | **exacto** |
| `MCONTA`, `MERCP`, `MCAJBA`, `MGENER` son nodos con hijos | **4/4 correcto** |
| `MEGAA`, `MCO511` son hojas | **2/2 correcto** |

Lo que el export agrega y esta nota no anticipaba:

- **La profundidad llega a 6 niveles**, no 2-3. La sección 2 acierta en que es
  variable, pero el rango real es más amplio: 719 códigos a 1 nivel, 1372 a 4,
  353 a 6.
- **794 códigos (23%) no llegan a `MENU`**: 717 no tienen padre (son su propia
  raíz, ej. `AG001`, `AC002`) y 44 apuntan a un padre que no existe como fila
  (`ANUREC`, `ASEGSOC`, ...). El export es una foto parcial.
- **2 ciclos** en las cadenas de padres.
- 194 nodos con hijos, 3195 hojas.

Cobertura sobre nuestro corpus: de 2213 `document_id` distintos, 1523 (68,8%)
están en el árbol y **1199 (54,2%) resuelven camino hasta `MENU`**.

### La convención `M` de la sección 4 tiene un contraejemplo `[VERIFICADO-CORPUS]`

Antes de tener el árbol se infirió que `M<letras><dígitos>` = hoja de
mantenimiento y `M` sin dígitos = carpeta. Verificado contra el árbol:

- `M` con dígitos: 942 códigos, **942 hojas**. Esta nota decía "941 hojas y 1
  nodo", con `MA6835` como "carpeta de menú indistinguible por patrón". **Era un
  artefacto de datos**: esa fila es su propio padre —un self-loop, y uno de los
  dos ciclos que detecta el mapa de procesos— así que el único "hijo" que tiene
  es él mismo. Su tipo de ventana declarado es 10, "Tabla general". Ver
  [visualtime-window-types.md](visualtime-window-types.md).
- `M` sin dígitos: 112 códigos, 102 nodos y 10 que la heurística de hijos daba
  por hojas (`MEGAA`, `MACPER`, `MATARILE`, `MCLA`, ...). **`MEGAA` no es una
  hoja**: el export lo declara tipo 8, "Menú". Es un menú vacío, y una
  declaración le gana a una inferencia sacada de la ausencia de hijos. Son 16 los
  casos así.

Confirma lo que la sección 3 ya decía: la regla estructural es preferible al
patrón del código. La precisión del patrón, cuando no hay árbol, es 941/942.

### Clasificar por nombre de archivo es un proxy pobre `[VERIFICADO-CORPUS]`

Distribución sobre los 2169 `.md` del corpus, clasificando por el *stem* del
nombre de archivo:

| Patrón | Archivos | Ejemplos |
|---|---|---|
| `^M[A-Z]{1,3}\d+` (mantenimiento?) | 669 | `ma0001`, `ma0004` |
| resto (funcional/ABM?) | 539 | `cp001`, `cp002` |
| `^[A-Z]{2}L\d+` (proceso/reporte) | 359 | `cpl001`, `cpl004` |
| con `-` o `_` (sub-página?) | 318 | `accounting_cpl500`, `bc005_k` |
| `^[A-Z]{2,3}C\d+` (consulta) | 177 | `cpc001`, `auc001` |
| `^INT\d+` (interfaz) | 107 | `int54050`, `int54051` |

Dos problemas visibles en esa tabla, que confirman la sección 5:

1. La categoría "con `-` o `_`" mezcla sub-páginas reales (`bc005_k`) con
   archivos cuyo nombre lleva el módulo como prefijo (`accounting_cpl500`, que
   es la transacción `CPL500`, no una sub-página). El separador en el nombre
   **no** implica sub-página.
2. El 669 de `^M[A-Z]{1,3}\d+` no son 669 mantenimientos: por la sección 3, los
   que sean nodos con hijos son carpetas de menú. Sin `WINDOWS` no se puede
   separar.

**Conclusión:** el código autoritativo se toma del **contenido** del documento;
el nombre de archivo sirve como fallback y nada más.

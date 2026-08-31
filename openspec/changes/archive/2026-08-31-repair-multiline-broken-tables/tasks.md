# Tareas de implementación

## 1. Tercera forma: filas multi-línea

- [x] 1.1 Permitir que un bloque candidato arranque con una línea sin pipe,
      cuando esté seguida inmediatamente por una línea que empieza con `|` —
      discriminador tenso, para no disparar con un `####` real seguido de prosa.
- [x] 1.2 Parseo por acumulación de celdas: línea sin pipe inicial = fila nueva;
      línea con pipe inicial = continuación de la fila en curso.
- [x] 1.3 Fila incompleta al cerrar: rellenar y advertir, como las otras formas.
- [x] 1.4 No romper las formas 1 (simple) y 2 (pareada) ya soportadas.

## 2. Tests

- [x] 2.1 Fixture real de `cash_and_banks/opl835.md` (5 columnas, filas de 1 y
      de 3 líneas) verificando que las celdas caen en la columna correcta.
- [x] 2.2 Fixture real de `accounting/cp001.md` (regla + código de error).
- [x] 2.3 El test negativo existente sigue pasando: un `####` real seguido de
      prosa no se toca.

## 3. Verificación y medición

- [x] 3.1 Bloques no reparados: 365 → medir.
- [x] 3.2 Regenerar el corpus y medir el nuevo conteo de chunks degenerados y
      de duplicados exactos.
- [x] 3.3 Reportar de qué son los degenerados que sobreviven, como insumo para
      la decisión de filtrado (que NO se toma en este cambio).

## 4. Alcance ampliado con evidencia

La recuperación (grupo 1) subió los chunks de tabla de 27.599 a 29.223 —**+1624
filas reales recuperadas**— pero los degenerados solo bajaron de 22,4% a 21,5%.
La mayoría tenía otra causa. Con esa medición ya en mano, el proposal decía
"decidir con evidencia", así que se decidió:

- [x] 4.1 Filtro `carries_no_information()`: descarta estructura markdown
      sobrante (`###  Proceso`, `#`), artefactos del export (`__`) y filas de
      tabla con todas sus celdas vacías.
- [x] 4.2 **El discriminador es contenido, no largo.** `No aplica.`,
      `A petición del usuario.` y `Volver a ejecutar.` son cortos pero son
      respuestas reales: con su header contextual dicen "la frecuencia de
      ejecución de CPL500 es: a petición del usuario". Filtrar por largo habría
      borrado 291 respuestas reales — el mismo error que habría sido filtrar los
      encabezados de las tablas rotas en vez de repararlas.
- [x] 4.3 Un heading cuenta como estructura solo si su texto es una etiqueta de
      ≤3 palabras: el export también emite `# ` para continuaciones de bullets
      que sí llevan contenido (`# § _Se construye el auxiliar..._`), y tratar
      toda línea con `#` como estructura habría borrado reglas reales. Con test.
- [x] 4.4 Tests tabla-dirigidos de los dos lados del discriminador, más una
      aserción de que ningún chunk producido es solo estructura.

## 5. Resultado medido

| | Antes | Después |
|---|---|---|
| chunks | 66.634 | 61.901 |
| tokens | 5.430.585 | 5.118.072 |
| chunks de tabla | 27.599 | **29.223** |
| degenerados (≤6 palabras) | 14.930 (22,4%) | 11.235 (18,1%) |
| sus tokens | 658.063 (12,1%) | 497.320 (9,7%) |
| duplicados exactos | 6.570 | 5.451 |

−4733 chunks y −312.513 tokens de ruido, y **+1624 filas de tabla recuperadas**
al mismo tiempo. Los cortos que sobreviven son contenido real: `No aplica.`
(178), `Volver a ejecutar.` (141), `A petición del usuario.` (113),
`Formato: Página` (93), `La tabla es de valores fijos.` (93).

- [x] 5.1 141 tests, `ruff` y `validate_specs` en verde.
- [x] 5.2 Corpus regenerado y deltas integrados en `openspec/specs/`.

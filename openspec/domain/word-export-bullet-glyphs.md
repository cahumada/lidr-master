# Los glifos de viñeta del export de Word || The export's bullet glyphs

Referencia sobre el sistema FUENTE (los documentos funcionales de VisualTIME
tal como llegan exportados), no sobre nuestro código. Relevado el 2026-09-01
midiendo el corpus completo: 2171 archivos `.md` bajo
`D:\EspecificacionesFuncionales_md` y los 61.901 chunks que produjeron.

## El corpus escribe sus listas con glifos, no con markdown

Los documentos vienen de Word, y sus listas multinivel llegan como caracteres
literales al principio de la línea en vez de bullets de markdown
[VERIFICADO-CORPUS]:

| Glifo | Apariciones |
|---|---|
| `·` (U+00B7) | 4867 |
| `o` (la letra o, minúscula) | 3078 |
| `§` (U+00A7) | 2149 |

Cada línea llega separada de la anterior por una línea en blanco, así que para
cualquier parser de markdown son párrafos independientes, no una lista. La
jerarquía existe en el documento y **no existe en el texto**.

## El glifo NO es un indicador confiable de profundidad

Es la pregunta que se hace cualquiera que quiera anidar estas listas, así que
va medida. Se tomaron los 1.065 pares donde una unidad deja el enunciado
abierto (termina en `,` o `:`) y la siguiente lo continúa — pares en los que,
por construcción, el segundo tiene que ser hijo del primero
[VERIFICADO-CORPUS]:

| Transición | Veces | Inversa | Veces |
|---|---|---|---|
| `·` → `o` | 105 | `o` → `·` | 7 |
| `o` → `§` | 83 | `§` → `o` | 2 |
| `§` → `·` | 43 | `·` → `§` | 5 |

Las dos primeras filas son consistentes con el orden por defecto de las listas
multinivel de Word (`•`, `o`, `§`) y sostienen `·` > `o` > `§`: 12 documentos
exhiben los dos descensos. La tercera lo rompe, y está concentrada en 4
documentos que usan otra asignación de niveles: `INSCALCSTAMPTAX`,
`INSCALGROSSEARN`, `INSCALRETIIBB_RG`, `INSROUTINEANNULMENT`.

Precisión de las dos reglas de profundidad candidatas, evaluadas contra esos
pares [VERIFICADO-CORPUS]:

| Regla | Acierta | Falla | Precisión |
|---|---|---|---|
| Orden global `·` > `o` > `§` | 193 | 52 | **78,8%** |
| Orden por primera aparición en la sección | 187 | 58 | **76,3%** |

**Por qué importa el número**: 1 de cada 5 hijos colgaría del padre
equivocado. En un corpus de reglas de negocio de seguros eso no produce un
chunk peor, produce un chunk que afirma lo contrario del documento — una
condición anidada bajo la rama que no le corresponde. Por eso
`fix-dangling-lead-in-chunks` resolvió el enunciado partido por gramática y no
por jerarquía. El próximo que quiera anidar por glifo necesita superar 78,8%.

## Señal todavía sin medir

La profundidad de blockquote (`>`, `> >`) es una señal independiente que el
export también emite y que podría desempatar los casos donde el glifo falla
[HIPÓTESIS]. No se midió.

## Otro uso del mismo export: `#` para continuaciones de bullet

Ya documentado en el código y en la spec de `document-chunking`: el export
también emite `# ` al principio de líneas que son continuación de un bullet y
sí llevan contenido (`# § _Se construye el auxiliar concatenando..._` en
`accounting/cp002.md`) [VERIFICADO-CORPUS]. Por eso ni la segmentación de
transacciones puede partir por H1, ni el filtro de estructura puede tratar toda
línea con `#` como un heading vacío.

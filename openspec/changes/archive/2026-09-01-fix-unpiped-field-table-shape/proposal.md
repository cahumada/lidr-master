## Why

Este cambio sale de la misma investigación que `fix-dangling-lead-in-chunks`,
pero es otro defecto y otra capability. El segundo chunk degenerado más
frecuente del corpus era `No`, emitido 51 veces en MER001. No es un bullet
partido: es **una celda de tabla**.

`MER001` documenta la taxonomía de tipos de error, una tabla de 4 columnas. El
export la dejó sin pipes y sin separador, con las columnas como headings:

```
##  Valores definidos

####  Tipo de Error \(Descripción\)
####  Explicación del Tipo de Error
####  Tipo de Raíz del Error
####  Temporal

####  _1\. Especificaciones_

El error se debe a especificaciones incorrectas.

No
```

`table-repair` no la reconoce. Sus tres formas exigen un pipe en el cuerpo: la
**simple** que toda línea siguiente lleve `|`, la **pareada** un `|  valor` sin
celda izquierda, y la de **filas partidas** que la continuación abra con `|`.
Acá no hay ni un pipe: los valores son prosa pelada. El resultado es
que la sección se chunkea como narrativa y **cada celda se vuelve un chunk
suelto**: 191 chunks para ~48 filas. El nombre del tipo de error, su
explicación, su raíz y su bandera *Temporal* quedan en cuatro chunks distintos,
ninguno de los cuales dice a qué fila pertenece. La taxonomía de errores es
irrecuperable por retrieval.

El mismo patrón está en las secciones `Campos` — el catálogo de campos, que es
el contenido de más valor del corpus. En `CP001`:

```
##  Campos
####  Título
####  Descripción
####  _Moneda_
Código de la moneda en la que se lleva la contabilidad de esta compañía. ...
```

produce hoy un chunk narrativo con la descripción y **sin el nombre del campo**:

```
[Sección: Campos]
Código de la moneda en la que se lleva la contabilidad de esta compañía. ...
```

La palabra `Moneda` no está en el texto, ni en `metadata.field`. La pregunta
"¿qué es el campo Moneda de CP001?" no puede recuperarse. Eso es información de
negocio perdida en silencio, que es la regla no negociable de este repo.

**Medición** [VERIFICADO-CORPUS], con un detector que toma como columnas la
corrida de `####` **no itálicos** y como etiqueta de fila cada `####` itálico:

| | |
|---|---|
| Bloques con esta forma que el normalizador actual **ya** repara | 267 |
| Bloques con esta forma que quedan **sin reparar** | **415** en 407 archivos de 2171 |
| ...de dos columnas (`Código`/`Descripción`, `Título`/`Descripción`) | 396 |
| ...de tres o cuatro | 19 |
| Filas de tabla que esos bloques esconden | **2.982** |

Las firmas de encabezado no dejan lugar a dudas sobre si son tablas: 205
`('Código', 'Descripción')`, 188 `('Título', 'Descripción')`, 16
`('Campo', 'Descripción', 'Error/adv')`. Revisadas 18 firmas no canónicas a
mano, ninguna es un subtítulo genuino.

## What Changes

- **Una cuarta forma rota en `table-repair`**: N headings `####` **no
  itálicos** son las columnas, y cada `####` itálico posterior es la etiqueta
  de una fila cuyos valores son prosa pelada, sin ningún pipe. Se reconstruye
  como tabla markdown válida, igual que las tres formas ya soportadas. Corre
  como segunda pasada, sobre lo que las tres con pipes no reclamaron, así que
  el comportamiento de esas tres no cambia.
- **La itálica es el discriminador.** El corpus escribe `Título` /
  `Descripción` sin marcar y `_Moneda_` en itálica. Sin esa distinción la
  corrida `Título` / `Descripción` / `_Parte repetitiva_` se leería como tres
  columnas en vez de dos más un divisor de grupo.
- **Ante la duda no se repara, y se registra.** Una fila debe aportar
  exactamente un valor por columna, o ninguno. Rellenar una fila corta al final
  pondría el valor bajo el encabezado equivocado. Los bloques rechazados se
  loguean con sus encabezados y su cantidad de filas.
- **Dos bugs latentes que este cambio destapó**, ambos arreglados acá:
  - `_render_table` escapa como `\|` un pipe que es parte del texto de una celda,
    pero `_split_row` partía por **todo** pipe y descartaba lo que caía pasada
    la última columna. El render y el parseo ahora coinciden.
  - `carries_no_information` trataba cualquier línea única terminada en `:`
    como una fila de tabla vacía. Al repararse la tabla que venía debajo, el
    lead-in `Algunos posibles valores son:` quedaba solo y se borraba. Una fila
    renderizada lleva una línea por columna, así que ahora la prueba exige al
    menos dos líneas.

## Resultado medido

Corrida completa sobre los 2169 archivos, comparada contra el corpus con
`fix-dangling-lead-in-chunks` ya aplicado [VERIFICADO-CORPUS]:

| | Antes | Después |
|---|---|---|
| Chunks del corpus | 60.451 | 62.206 (+1.755) |
| ...de tipo `table` | 29.223 | **32.144** (+2.921) |
| ...de tipo `narrative` | 31.228 | 30.062 (−1.166) |
| Chunks con `metadata.field` | 28.075 | **30.993** (+2.918) |
| Bloques reparados / rechazados | — | **406 / 9** |
| Documentos | 2213 | 2213 |
| Documentos que perdieron **alguna palabra** | — | **0** |

Cero palabras perdidas en los 430 documentos que cambiaron: cada palabra que
estaba en un chunk antes sigue estando en algún chunk después. Lo que cambió es
cómo están agrupadas, y que ahora el nombre del campo viaja con su descripción.

**MER001 es uno de los 9 rechazados.** Sus filas tienen 2 o 3 valores para 4
columnas y el hueco no siempre está al final, así que rellenar pondría `No`
bajo *Tipo de Raíz del Error* en vez de *Temporal*. Sus 191 chunks siguen como
narrativa, ahora con una advertencia que los hace visibles. Recuperarlo exige
saber a qué columna corresponde cada valor suelto, que este cambio no sabe.

## Capabilities

### Modified Capabilities

- `table-repair`: reconoce una cuarta forma rota del export, la de headers y
  etiquetas sin pipes; registra las corridas que no puede reparar; y hace que
  el renderizado y el parseo de una celda coincidan en el pipe escapado.
- `document-chunking`: la prueba de fila vacía de `carries_no_information`
  exige al menos dos líneas, para no borrar una prosa de una línea que termina
  en dos puntos.

## Impact

- `app/generation/rag/chunking/normalizer.py` — la cuarta forma, su guarda de
  simetría y el log de rechazos.
- `app/generation/rag/chunking/functional_spec.py` — `_split_row` parte solo
  por pipes sin escapar; `carries_no_information` exige dos líneas para la
  prueba de fila vacía.
- `tests/generation/rag/test_unpiped_tables.py` — nuevo.
- `data/chunks/` — artefacto regenerado. Los ~2.900 chunks que pasan de
  narrativa a `table` cambian de `content_hash`.

## Lo que este cambio NO hace

- **No toca el enunciado partido** (`De lo contrario,`, 72 veces): ese es
  `fix-dangling-lead-in-chunks`, otra capability y otro discriminador.
- **No reordena ni renombra columnas.** Los headers del export se toman como
  vienen, incluso cuando dicen `Título` / `Descripción` en vez del nombre real
  del campo.
- **No recupera MER001** ni los otros 8 bloques asimétricos. Necesitan saber a
  qué columna corresponde cada valor suelto, y adivinarlo escribiría un hecho
  de negocio falso. Quedan registrados, no reparados.
- **No lleva los rechazos a `chunking_report.md`.** Se emiten como advertencia
  de `structlog`, que es como el normalizador ya reporta sus huecos; llevarlas
  al reporte markdown exige hacer viajar las trazas de reparación hasta
  `chunk_corpus.py`, que hoy las descarta.

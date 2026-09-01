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

`table-repair` no la reconoce. Su forma **simple** exige que toda línea
siguiente lleve `|`; su forma **pareada** exige un `|  valor` sin celda
izquierda. Acá no hay ni un pipe: los valores son prosa pelada. El resultado es
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

**Medición** [VERIFICADO-CORPUS]:

| | |
|---|---|
| Bloques en el fuente con ≥3 `####` consecutivos seguidos de contenido sin pipes | 420 en 402 archivos de 2171 |
| Documentos cuya sección `Campos`/`Valores definidos` derrama ≥3 chunks narrativos | 47 de 2250 |
| Chunks narrativos dentro de esas secciones | 1.416 (2,29% del corpus) |
| Solo MER001 / `Valores definidos` | 191 chunks |

Los 420 bloques son el detector crudo y sobrestima: incluye headings genuinos.
Los 47 documentos / 1.416 chunks son el síntoma confirmado aguas abajo. La
primera tarea de este cambio es cerrar esa horquilla antes de escribir código.

## What Changes

- **Una tercera forma rota en `table-repair`**: una corrida de N headings `####`
  seguida de bloques `#### <etiqueta de fila>` + prosa, **sin ningún pipe**. Se
  reconstruye como tabla markdown válida de N columnas, igual que las dos
  formas ya soportadas.
- **El disparador exige simetría, no solo la forma.** `####` también es un
  subtítulo legítimo — la spec ya protege ese caso. La reparación solo dispara
  cuando la corrida de headers va seguida de bloques con estructura repetida y
  consistente con el número de columnas. Ante la duda, no se repara: dejar la
  sección como narrativa mantiene el texto; repararla mal inventaría filas.
- **Lo que no se puede reparar, se advierte.** Una corrida de headers cuyo
  cuerpo no encaja se reporta en `chunking_report.md` con documento y sección,
  en vez de pasar en silencio. Una tabla rota que nadie ve es peor que una que
  falla ruidosamente.

## Capabilities

### Modified Capabilities

- `table-repair`: reconoce una tercera forma rota del export, la de headers sin
  pipes, y advierte sobre las corridas de headers que no puede reparar.

## Impact

- `app/generation/rag/chunking/normalizer.py` — la tercera forma y su guarda.
- `scripts/` — el reporte de corridas de headers no reparadas.
- `tests/generation/rag/chunking/` — fixtures de MER001 y CP001.
- `data/chunks/` — regenerado. Los ~1.416 chunks afectados cambian de
  `chunk_type` narrativo a `table` y cambian de `content_hash`.

## Lo que este cambio NO hace

- **No toca el enunciado colgado** (`De lo contrario,`, 72 veces): ese es
  `fix-dangling-lead-in-chunks`, otra capability y otro discriminador.
- **No reordena ni renombra columnas.** Los headers del export se toman como
  vienen, incluso cuando dicen `Título` / `Descripción` en vez del nombre real
  del campo.

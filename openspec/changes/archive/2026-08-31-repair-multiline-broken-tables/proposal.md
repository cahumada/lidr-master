## Why

Al agregar `content_hash` aparecieron 6570 chunks duplicados exactos, y al
inspeccionarlos, **14.930 chunks (22,4%) degenerados** —≤6 palabras de
contenido real— consumiendo **658.063 tokens (12,1%)**. Los más frecuentes son
headings sueltos: `'####  Campo'` (x169), `'####  Operador'` (x162),
`'####  Valor'` (x162), `'####  Observación'` (x161).

La lectura fácil habría sido "filtrar chunks cortos". **Sería un error grave.**
Al mirar la fuente, esos `####` no son ruido: son los encabezados de columna de
un **tercer tipo de tabla rota** que la reparación no reconoce.

`cash_and_banks/opl835.md`:

```
####  Información   ####  Campo   ####  Operador   ####  Valor   ####  Observación

Número de solicitud            ← esta línea NO tiene "|"
|  nRequest\_nu
| > | 0 | Se deben tomar en cuenta todas las solicitudes de cheque
```

Esas tres líneas son **una fila**. `_find_candidate_blocks` exige que después de
la corrida de `####` venga inmediatamente una línea con `|`; acá viene una línea
sin pipe (la primera celda de la fila, sola), así que el bloque no califica y la
reparación desiste.

**Qué se está destruyendo:** son condiciones de búsqueda
(tabla/campo/operador/valor) y reglas de validación con su código de error.
`accounting/cp001.md` tiene `'Debe incluir el ejercicio'` + `'| 736024'` — una
regla y su código, hoy partidos en chunks inservibles.

Alcance medido: **365 bloques en 208 archivos**. Hoy la reparación acierta 2367
bloques y se pierde estos 365.

Filtrar los chunks cortos habría **borrado reglas de negocio de seguros** y
dejado el defecto invisible para siempre. Recuperarlas las convierte en filas de
tabla, que es lo que son.

## What Changes

- **Tercera forma de tabla rota** en `repair_broken_tables`: encabezados `####`
  seguidos de filas que pueden abarcar varias líneas. Una línea **sin** pipe
  inicial empieza una fila nueva; una línea **con** pipe inicial continúa la
  fila en curso.
- **Medición del residuo**: después de recuperar, volver a medir qué chunks
  degenerados quedan y de qué son, para decidir con evidencia si hace falta
  filtrar algo — en vez de asumirlo ahora.

## Capabilities

### Capabilities modificadas

- `table-repair`: la tercera forma, con filas multi-línea.

## Impact

- `app/generation/rag/chunking/normalizer.py` — detección y parseo de la forma 3.
- `tests/generation/rag/test_normalizer.py` — fixture real de `opl835.md`.
- `data/chunks/` — regenerar.

## Fuera de alcance

**Filtrar o marcar los chunks degenerados que queden.** Primero hay que ver
cuántos sobreviven a la recuperación y de qué son. Si después de esto quedan
artefactos como `'__'` (x179), esa decisión —descartar o marcar, y con qué
umbral— repite la asimetría del documento índice y merece su propia evidencia.
No se decide sobre un número que este cambio va a mover.

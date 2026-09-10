# Diseño

## 1. La causa raíz es que «módulo» significa dos cosas

Para una persona que conoce VisualTIME, el módulo de `CA014` es «CA» — el
prefijo con el que se nombran las transacciones de pólizas. Para el corpus, el
`module_code` de `CA014` es `DMECAR`, el código del nodo módulo del árbol
`WINDOWS` de donde el chunker derivó el breadcrumb.

Las dos son ciertas. El defecto no es que una esté mal, es que el código toma la
palabra de la persona y la usa como si fuera la del corpus.

Todo lo que sigue sale de no forzar esa equivalencia.

## 2. Se quita el filtro derivado de la pregunta, no se arregla

Tres razones, en orden de peso:

**No hay comportamiento que preservar.** El filtro emite `"CA"` y el corpus
guarda `DMECAR`: no matcheó nunca. Quitarlo no puede regresionar nada, solo
puede dejar de restar evidencia. Es el caso raro en que borrar código es la
opción conservadora.

**El camino que necesitaba ya existe.** La spec de `retrieval` declara la rama
de coincidencia exacta precisamente porque *"el corpus se habla por código: un
usuario pregunta por `CAC011`, por la tabla `premium_mo`, por el campo
`nReceipt`"*. Una pregunta que nombra `CA014` ya lo encuentra por
`document_id`. El filtro de módulo encima solo puede recortar de más.

**Aun arreglado seguiría siendo una adivinanza.** Ver la medición del proposal:
`OPL` cae en 5 módulos y `MA` en 4. Cualquier versión «correcta» de la
heurística tendría que elegir uno y perder la cola.

**Alternativa descartada — validar contra el vocabulario y descartar si no
matchea.** Deja el código vivo para que la próxima persona lo «mejore», y no
aporta nada: el resultado útil de esa validación es siempre «descartar».

## 3. El anchor de módulo se resuelve por prefijo, no por `module_code`

Acá **no** se puede quitar nada: *«de acá en adelante, solo módulo CA»* es una
instrucción explícita del usuario. Ignorarla sería tan malo como aplicarla mal.

Lo que se puede es dejar de traducirla a un vocabulario ajeno. El usuario dice
«las transacciones que empiezan con CA», y eso es expresable **sin adivinar**:
un filtro por prefijo de `document_id`. No es un `module_code` y no debe
llamarse así.

| lo que fija el usuario | dimensión | se aplica sobre |
|---|---|---|
| «módulo CA» | prefijo de transacción | `document_id LIKE 'CA%'` |
| el selector de la consola | `module_code` | `module_code IN (...)` |

Son **dos filtros distintos** que pueden convivir, y ninguno de los dos es una
inferencia: los dos se aplican exactamente a lo que nombran.

**Alternativa descartada — que el anchor de módulo se rechace al fijarse.**
Sería honesto (no aplica algo que no puede resolver) y peor de usar: el usuario
escribió una frase perfectamente clara y el sistema le contestaría que no la
entiende, cuando sí la entiende.

**Alternativa descartada — ampliar `_MODULE` a `[A-Za-z]{2,7}` para que capture
`DMECAR`.** No arregla el caso real —nadie dice «módulo DMECAR»— y agrega un
segundo camino que sí matchea, dejando el vocabulario partido en dos según
cuánto escribió el usuario.

## 4. La regla que tiene que sobrevivir a este change

> Un valor de filtro fuera de su vocabulario NUNCA se aplica en silencio.

Es lo que convierte esto en algo más que dos arreglos puntuales. Los dos
defectos —la heurística y el anchor— fueron invisibles durante semanas porque un
filtro que recorta a la nada se ve igual que una pregunta sin respuesta en el
corpus. `fix-dropped-agentic-filters` puso `effective_filters` con su origen en
la respuesta, y ese es el mecanismo que dejó ver esto; la regla lo vuelve
normativo para el próximo productor de filtros que alguien agregue.

Y su corolario, que ya está en la spec de `answer-orchestration`: un filtro
**explícito** que no matchea nada SÍ debe devolver cero — alguien lo pidió. Lo
que no se aplica es el que nadie pidió o el que no se puede resolver.

## 5. Sobre el orden en que conviene hacerlo

El punto 2 (quitar la heurística) es una línea y arregla el caso más frecuente
—cualquier pregunta que nombre una transacción—, así que va primero y se puede
verificar solo.

El punto 3 (el prefijo como dimensión) toca el repositorio, el `kind` del anchor
y la spec de `conversation-memory`. Si hubiera que partir el change, ese es el
corte natural.

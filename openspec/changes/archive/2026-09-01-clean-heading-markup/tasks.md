# Tareas de implementación

## 1. Los patrones dejan de cruzar líneas

- [x] 1.1 `\s` → `[ \t]` en `TITLE_PATTERN`, `H1_PATTERN` y `H2_PATTERN`, con el
      comentario de por qué `re.MULTILINE` no alcanza.
- [x] 1.2 Test: `##\n\n## Notas al programador` produce la sección
      `Notas al programador`, no una llamada `## Notas al programador`.
- [x] 1.3 Test: `##\n\nTexto cualquiera` NO crea una sección fantasma llamada
      `Texto cualquiera`.
- [x] 1.4 Test: `#\n\n# Título` no deja el título como `# Título`.
- [x] 1.5 Revisar `_ID_MARK` (`[\s\`*]*`), que tiene el mismo `\s` en un
      patrón `^...$` con MULTILINE.

## 2. `heading_text()`

- [x] 2.1 La función, con la convención bilingüe, en el orden: glifo de viñeta,
      marcadores `#`, link, énfasis, escapes del export, colapso de espacios.
- [x] 2.2 Un `*` interior colapsa a un espacio.
- [x] 2.3 Un `_` interior entre alfanuméricos NO se toca — regla de CommonMark.
      Con `Conteo de unidades por unit_type` como test.
- [x] 2.4 `[Campos](../x.html)` → `Campos`; un link sin etiqueta no rompe.
- [x] 2.5 Reemplazar `_strip_emphasis` en los puntos donde nombra algo, dejando
      los demás como están.
- [x] 2.6 Tests con los 13 headings reales de marcador interior del corpus.

## 3. Verificación sobre el corpus

- [x] 3.1 Chunks con ruido de marcado en el header: 5.551 → medir.
- [x] 3.2 `metadata.section` distintas: que `Proceso batch` deje de tener tres
      grafías.
- [x] 3.3 Sin pérdida: mismos documentos, ninguno en cero chunks, ningún chunk
      narrativo sobre el techo de 500 tokens.
- [x] 3.4 Contar cuántos `chunk_id` cambian y por qué.

## 4. Cierre

- [x] 4.1 `pytest`, `ruff check .` y `validate_specs.py` en verde.
- [x] 4.2 Regenerar `data/chunks` y re-embeber incremental.
- [x] 4.3 Promover el delta y archivar.


## Resultados medidos

| | antes | ahora |
|---|---:|---:|
| chunks con marcado en el header | 5.260 | **2** |
| chunks con marcado en `metadata.section` | 2.553 | **0** |
| `metadata.section` distintas | 338 | 270 |
| chunks | 62.206 | 62.228 |
| documentos | 2.213 | 2.213 |
| documentos en cero chunks | 2 | 2 |
| chunks narrativos sobre el techo de 500 | 0 | 0 |

Los 2 que quedan son contenido literal, no marcado: `\#Número de página` en un
layout de reporte de CAL507 y `\# 1` en CAL516. El escape se deshizo y el `#`
que queda es el carácter que el documento quiere decir.

Los backticks se conservan a propósito: `` `<DF009>` `` es el marcador de
personalización por cliente que el diseño preserva, y `` `IBNR` `` es el nombre
de una tabla. Quitarlos borraría significado, no ruido.

Re-embedding incremental: 41.919 filas reutilizadas, 15.212 nuevas, US$ 0,0303,
0 lotes fallidos, verificación en disco OK.

## La regresión que casi se publica

La primera versión de `heading_text` limpiaba `## [](../mantenimiento/ma0085.html)`
—un link cuya etiqueta perdió el export— hasta la cadena vacía. Un heading sin
nombre es *junk*, y descartar un heading junk **se lleva su cuerpo**: MS010
perdió sus siete reglas de validación con sus códigos de error, y el código
`10208` desapareció del corpus entero.

Lo detectó el invariante de no-pérdida, no los tests: los tests afirmaban el
comportamiento equivocado (`("[](sin-etiqueta.html)", "")` estaba escrito como
si devolver vacío fuera correcto). El test se corrigió junto con el código.

Es la tercera vez en este repo que la regla es la misma: **marcar o recuperar,
nunca borrar**. Un heading que perdió su etiqueta conserva su destino como
nombre.

## Hallazgos

- **`re.MULTILINE` no impide que `\s+` cruce un `
`.** Era la causa de fondo,
  y no era cosmética: 62 archivos con un heading tragado y 68 secciones fantasma
  cuyo nombre era un párrafo del cuerpo.
- **`_strip_emphasis` solo miraba los bordes.** `**Proceso****Batch**` perdía sus
  marcadores externos y conservaba los interiores, dejando tres grafías de la
  misma sección que no agrupaban entre sí.
- **El `_` de `unit_type` no es énfasis.** CommonMark ya lo dice; sin esa regla,
  limpiar el énfasis habría roto los identificadores del dominio.
- **El blockquote escuda al marcador de heading.** `> ### Proceso` sobrevivía a
  un stripper que solo miraba `#` al principio: 211 headers.

# Tareas de implementación

## 1. Cerrar la horquilla de la medición

- [x] 1.1 Detector preciso: la corrida de `####` **no itálicos** son las
      columnas, cada `####` itálico posterior es etiqueta de fila. Medido
      contra el corpus y contra el normalizador actual para separar lo que ya
      se repara de lo que falta.
- [x] 1.2 Revisadas 18 firmas de encabezado no canónicas a mano: ninguna es un
      subtítulo genuino. Las canónicas (`Código`/`Descripción`,
      `Título`/`Descripción`, `Campo`/`Descripción`/`Error/adv`) cubren 409 de
      los 415 bloques.
- [x] 1.3 `proposal.md` actualizado: 267 bloques ya reparados, **415 sin
      reparar** en 407 archivos, 2.982 filas escondidas. Reemplaza la horquilla
      de 420 bloques / 47 documentos.

## 2. La cuarta forma en el normalizador

- [x] 2.1 `_find_unpiped_blocks` + `_read_unpiped_block`: reconstruyen la
      corrida de N headers como fila de encabezado + separador `---`, y cada
      bloque `#### _etiqueta_` + prosa como una fila. Corre como segunda
      pasada, fuera de lo que las tres formas con pipes ya reclamaron.
- [x] 2.2 Guarda de simetría `_unpiped_rows_are_symmetric`: cada fila aporta un
      valor por columna, o ninguno. Ante la duda, no se repara.
- [x] 2.3 El texto antes y después del bloque reparado vuelve byte por byte
      igual — cubierto por los tests negativos.
- [x] 2.4 Test: una corrida de 4 columnas con filas desparejas (la forma de
      MER001) NO se repara y el texto vuelve intacto.
- [x] 2.5 Test con la forma de CP001: `Campos` produce filas donde
      `metadata.field` es `Moneda` y el texto lleva `Título: Moneda`.
- [x] 2.6 Test negativo: `#### Paso uno` + prosa, `#### Paso dos` + prosa no se
      repara.
- [x] 2.7 Test: un miembro itálico de la corrida (`_Parte repetitiva_`) es
      etiqueta de fila, no una tercera columna.

## 3. Bugs latentes que el cambio destapó

- [x] 3.1 `_split_row` parte solo por pipes sin escapar y desescapa `\|`. El
      render escapaba y el parseo no desescapaba, así que una celda con un pipe
      se cortaba en dos y lo que caía pasada la última columna se descartaba.
- [x] 3.2 `carries_no_information` exige al menos dos líneas para la prueba de
      fila vacía. Sin ese piso borraba `Algunos posibles valores son:` en cinco
      secciones `Valores posibles`, una vez reparada la tabla de abajo.
- [x] 3.3 Tests de ambos.

## 4. Registrar lo que no se puede reparar

- [x] 4.1 Cada corrida que la guarda rechaza se loguea con sus encabezados, su
      cantidad de filas y la razón.
- [ ] 4.2 Llevarlas a `chunking_report.md`. Requiere hacer viajar las trazas de
      reparación desde el normalizador hasta `chunk_corpus.py`, que hoy las
      descarta con `_table_traces`. Queda fuera de este cambio.

## 5. Verificación sobre el corpus

- [x] 5.1 Corpus regenerado: 406 bloques reparados, 9 rechazados. Los chunks
      `table` suben de 29.223 a 32.144 y los que llevan `metadata.field` de
      28.075 a 30.993.
- [x] 5.2 Ninguna sección pasa a producir cero chunks; 2213 documentos antes y
      después.
- [x] 5.3 **Cero palabras perdidas** en los 430 documentos que cambiaron: cada
      palabra que estaba en un chunk antes sigue en algún chunk después. Las
      advertencias de reparación del normalizador son las mismas 45 + 4044 que
      antes del cambio, así que no se introdujo ninguna pérdida nueva.

## 6. Cierre

- [x] 6.1 `pytest` (224), `ruff check .` y `validate_specs.py` en verde.
- [ ] 6.2 Integrar los deltas en `openspec/specs/` y archivar el cambio.
- [ ] 6.3 Regenerar `data/chunks` y volver a correr embeddings — decisión del
      dueño del repo.

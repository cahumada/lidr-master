# Tareas de implementación

## 1. Cerrar la horquilla de la medición

- [ ] 1.1 Detector preciso de la forma: corrida de N `####` seguida de bloques
      `#### <etiqueta>` + prosa sin pipes. Contar bloques, archivos y chunks
      afectados, y separarlos de los headings genuinos.
- [ ] 1.2 Revisar a mano 15 bloques del detector: cuántos son tabla real y
      cuántos son subtítulos legítimos. El número de falsos positivos decide
      cuán estricta tiene que ser la guarda de 2.2.
- [ ] 1.3 Actualizar el `proposal.md` con el número cerrado, reemplazando la
      horquilla 420 bloques / 47 documentos.

## 2. La tercera forma en el normalizador

- [ ] 2.1 Reconstruir la corrida de N headers como fila de encabezado +
      separador `---`, y cada bloque `#### <etiqueta>` + prosa como una fila.
- [ ] 2.2 Guarda de simetría: solo reparar cuando los bloques que siguen tienen
      estructura repetida y consistente con las N columnas. Ante la duda, no
      reparar.
- [ ] 2.3 El texto antes y después del bloque reparado vuelve byte por byte
      igual, como ya exige la spec para las otras dos formas.
- [ ] 2.4 Test con el fixture de MER001: `Valores definidos` produce ~48 filas
      con sus 4 celdas, no 191 chunks sueltos.
- [ ] 2.5 Test con el fixture de CP001: `Campos` produce filas donde
      `metadata.field` es `Moneda` y el texto lleva `Título: Moneda`.
- [ ] 2.6 Test negativo: una corrida de `####` seguida de prosa sin estructura
      repetida NO se repara y el texto vuelve intacto.

## 3. Advertir lo que no se puede reparar

- [ ] 3.1 Registrar cada corrida de headers que la guarda rechaza, con
      documento y sección.
- [ ] 3.2 Exponerla en `chunking_report.md`, junto al resto de las advertencias
      del corpus.
- [ ] 3.3 Test: una corrida rechazada aparece en el reporte.

## 4. Verificación sobre el corpus

- [ ] 4.1 Regenerar `data/chunks/` y verificar que MER001 `Valores definidos`
      baja de 191 chunks narrativos a filas de tabla.
- [ ] 4.2 Ninguna sección que hoy produce chunks pasa a producir cero.
- [ ] 4.3 Comparar el total de chunks antes y después, y explicar la diferencia
      documento por documento para los 10 más afectados.

## 5. Cierre

- [ ] 5.1 `uv run pytest`, `uv run ruff check .`,
      `uv run python scripts/validate_specs.py` en verde.
- [ ] 5.2 Integrar el delta en `openspec/specs/table-repair/spec.md` y archivar.

# Tareas de implementación

## 1. El grafo

- [ ] 1.1 `graph.py`: nodo = transacción, arista = `(source, target, edge_type,
      origin)`. Los tres tipos nunca colapsados.
- [ ] 1.2 Aristas `menu_parent` desde `WINDOWS.parent_code`.
- [ ] 1.3 Aristas `references` desde las `references` del chunk y los enlaces
      HTML, marcando cuáles vienen de un documento índice.
- [ ] 1.4 Detección de ciclos: el árbol ya tuvo uno, y un mapa con un ciclo
      cuelga a quien lo recorra.

## 2. Precedencia declarada

- [ ] 2.1 `requisites.py`: reconocer el enunciado de precedencia en la sección
      `Requisitos`.
- [ ] 2.2 Tomar los códigos de lo que sigue al enunciado, no de toda la sección.
- [ ] 2.3 Un `Requisitos` sin enunciado de precedencia no aporta aristas.
- [ ] 2.4 Tests con los casos reales: `CO501`, `COL502`, `COL520`, `SIL500`.
- [ ] 2.5 Test negativo: un `Requisitos` de permisos no genera una arista.

## 3. Cobertura, dicha y no omitida

- [ ] 3.1 Contar: transacciones sin menú, nodos sin documento, documentos que no
      son ventana.
- [ ] 3.2 Esos números van en el artefacto **y** en el contexto del CAG.
- [ ] 3.3 `process_map_report.md`.

## 4. El contexto del CAG

- [ ] 4.1 `cag.py`: renderizar jerarquía + catálogo + dependencias + los huecos.
- [ ] 4.2 Contar tokens con `count_tokens`, no estimar.
- [ ] 4.3 Superar el techo **falla**; no trunca.
- [ ] 4.4 Test: el contexto declara sus límites, no solo los datos.

## 5. Persistencia

- [ ] 5.1 `process_map_edges` con índices en las dos puntas.
- [ ] 5.2 Migración de Alembic.
- [ ] 5.3 Carga idempotente.
- [ ] 5.4 Test de integración: expandir por referencias desde un documento.

## 6. Batch y cierre

- [ ] 6.1 `scripts/build_process_map.py` con `--dry-run`.
- [ ] 6.2 Corrida real: medir nodos, aristas por tipo y tokens del contexto.
- [ ] 6.3 `pytest`, `pytest -m integration`, `ruff` y `validate_specs` en verde.
- [ ] 6.4 Promover el delta y archivar.

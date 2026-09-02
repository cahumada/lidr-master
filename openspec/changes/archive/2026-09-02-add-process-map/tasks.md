# Tareas de implementación

## 1. El grafo

- [x] 1.1 `graph.py`: nodo = transacción, arista = `(source, target, edge_type,
      origin)`. Los tres tipos nunca colapsados.
- [x] 1.2 Aristas `menu_parent` desde `WINDOWS.parent_code`.
- [x] 1.3 Aristas `references` desde las `references` del chunk y los enlaces
      HTML, marcando cuáles vienen de un documento índice.
- [x] 1.4 Detección de ciclos: el árbol ya tuvo uno, y un mapa con un ciclo
      cuelga a quien lo recorra.

## 2. Precedencia declarada

- [x] 2.1 `requisites.py`: reconocer el enunciado de precedencia en la sección
      `Requisitos`.
- [x] 2.2 Tomar los códigos de lo que sigue al enunciado, no de toda la sección.
- [x] 2.3 Un `Requisitos` sin enunciado de precedencia no aporta aristas.
- [x] 2.4 Tests con los casos reales: `CO501`, `COL502`, `COL520`, `SIL500`.
- [x] 2.5 Test negativo: un `Requisitos` de permisos no genera una arista.

## 3. Cobertura, dicha y no omitida

- [x] 3.1 Contar: transacciones sin menú, nodos sin documento, documentos que no
      son ventana.
- [x] 3.2 Esos números van en el artefacto **y** en el contexto del CAG.
- [x] 3.3 `process_map_report.md`.

## 4. El contexto del CAG

- [x] 4.1 `cag.py`: renderizar jerarquía + catálogo + dependencias + los huecos.
- [x] 4.2 Contar tokens con `count_tokens`, no estimar.
- [x] 4.3 Superar el techo **falla**; no trunca.
- [x] 4.4 Test: el contexto declara sus límites, no solo los datos.

## 5. Persistencia

- [x] 5.1 `process_map_edges` con índices en las dos puntas.
- [x] 5.2 Migración de Alembic.
- [x] 5.3 Carga idempotente.
- [x] 5.4 Test de integración: expandir por referencias desde un documento.

## 6. Batch y cierre

- [x] 6.1 `scripts/build_process_map.py` con `--dry-run`.
- [x] 6.2 Corrida real: medir nodos, aristas por tipo y tokens del contexto.
- [x] 6.3 `pytest`, `pytest -m integration`, `ruff` y `validate_specs` en verde.
- [x] 6.4 Promover el delta y archivar.


## Resultados medidos

| | |
|---|---:|
| Nodos | **4.061** |
| Aristas | **4.101** |
| — `menu_parent` | 2.672 |
| — `references` | 1.390 (676 desde documentos índice) |
| — `requires` | **39** |
| Contexto del CAG | **90.067 tokens** (70% del techo de 128k) |
| Aristas en Postgres | 4.101, idempotente |

Tests: 353 con la base levantada. La expansión responde preguntas reales:
*"quién requiere `COL500`"* → `CO501`, `COL502`, `COL520`, `COL704`, `COL742`;
*"qué requiere `MGSL006`"* → sus 6 procesos.

## Correcciones sobre lo propuesto

**"No alcanzable desde el menú" son 794, no 714.** El proposal contaba los
códigos sin padre. Pero 3 de esos **tienen hijos**, y cada descendiente de un
subárbol colgado de la nada es tan inalcanzable como su raíz. La medida correcta
es si el camino llega a la raíz —lo que `NavigationTree.path()` ya resuelve, y a
prueba de ciclos—. Contar solo los sin padre subcontaba por 80.

Lo encontró un test que escribí con una expectativa equivocada: armé un árbol
donde `MENU` no tenía hijos, así que quedaba marcado como inalcanzable. El
código tenía razón sobre esos datos; la definición era la imprecisa.

**Faltaba un enunciado de precedencia.** `CRL663` escribe *"Antes de la
ejecución de este proceso se deben ejecutar los siguiemtes otros"* —con el typo
del fuente— y no matcheaba. Se agregó `antes de la ejecución`, que es el
enunciado; matchear la frase de la lista (*"los siguientes"*) no habría
sobrevivido al typo. Con eso, 24→25 documentos y 37→39 aristas.

## Cambios de infraestructura

`NavigationTree` ganó cuatro accesores de solo lectura (`codes`, `parent_of`,
`description_of`, `has_children`). El builder necesita recorrer el árbol entero
y la alternativa era meterse con sus diccionarios privados.

## Lo que quedó dicho como límite, y no como nota al pie

El contexto del CAG **empieza** declarando qué no cubre: que 794 transacciones no
cuelgan de un menú y que eso no significa que no existan, que `references` no
implica dependencia, y que fuera de las 39 `requires` la documentación no dice en
qué orden se ejecutan los procesos.

Va adentro del contexto y no al lado, porque un modelo que reciba el mapa sin sus
límites va a contestar que una transacción no existe cuando lo que pasa es que no
está en el menú.

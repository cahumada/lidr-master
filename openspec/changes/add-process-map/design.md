# Decisiones de diseño

## 1. Cada arista lleva su fuente, y las fuentes no se mezclan

Tres relaciones distintas conviven en el corpus y no tienen la misma fuerza:

| tipo | de dónde sale | qué afirma |
|---|---|---|
| `menu_parent` | `WINDOWS.parent_code` | dónde vive la transacción en el menú |
| `requires` | sección `Requisitos` | que **hay que** ejecutar A antes de B |
| `references` | enlace o mención | que un documento **habla de** otro |

Colapsarlas en un grafo homogéneo destruye la información que las hace útiles.
`requires` es una afirmación del negocio; `references` desde un documento índice
es una tabla de contenidos. Un consumidor que las vea iguales concluirá que
`LIFE_INDEX` tiene 130 dependencias de proceso.

Por eso el tipo y la fuente viajan **en la arista**, no en una convención.

## 2. Los huecos son parte del mapa, no una nota al pie

714 transacciones no cuelgan de ningún menú. 1.850 nodos del árbol no tienen
documento funcional. 672 documentos no son una ventana.

Ninguno de esos tres números es un error a corregir: son cómo es el sistema. Un
mapa que los omitiera se leería como completo y llevaría a conclusiones falsas
—"esta transacción no existe" cuando lo que pasa es que no está en el menú—.

Van en el reporte y en el artefacto, con su nombre. Y el contexto del CAG los
declara, para que el modelo que lo lea sepa qué no puede afirmar.

## 3. El `Requisitos` se parsea del enunciado más la tabla, no de una regexp sobre el texto

La dependencia está partida en dos: el enunciado dice la semántica
(*"requiere que previamente se ejecute"*) y la tabla que sigue da los códigos
(`[COL500](col500.html) | Generación...`).

Buscar códigos con una regexp sobre toda la sección traería también los
mencionados de paso, y perdería la dirección: `A requiere B` y `B requiere A` se
escriben con los mismos dos códigos.

**Se hace en dos pasos:** reconocer el enunciado que declara precedencia, y
recién entonces tomar los códigos de lo que le sigue. Un `Requisitos` sin
enunciado de precedencia no aporta aristas — tiene requisitos de otra clase
(permisos, datos cargados) que no son precedencia entre procesos.

**Costo aceptado:** cobertura menor que una regexp ciega. Preferible: una arista
inventada en un mapa de procesos es peor que una arista faltante, porque el mapa
se va a usar para responder "qué tengo que correr antes".

## 4. El contexto del CAG se genera, con su tamaño medido

95.100 tokens medidos con el mismo `count_tokens` que usa el chunker, no
estimados por caracteres. El techo va en `Settings`, y si el contexto lo supera
el build **falla** en lugar de entregar algo que se va a truncar en silencio —
truncar un mapa por la mitad es peor que no tenerlo, porque lo que queda parece
completo.

Si algún día no entra, el recorte tiene un orden pensado: primero los nodos sin
documento (no hay nada que responder sobre ellos), después el catálogo de
documentos (eso lo cubre el RAG), y último la jerarquía y las dependencias, que
son lo que el RAG **no** puede reconstruir por similitud.

## 5. El artefacto es JSON y la tabla es para expandir

Dos consumidores distintos:

- **El contexto del CAG** se precarga entero: un archivo de texto.
- **La recuperación** necesita preguntar "¿qué referencia a `CA014`?" para una
  consulta puntual. Cargar el JSON entero para eso sería absurdo.

De ahí la tabla `process_map_edges`: `(source, target, edge_type, origin)`, con
índices en las dos puntas. Es el mismo dato en la forma que cada uno necesita, y
el JSON sigue siendo la fuente reproducible.

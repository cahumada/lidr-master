# Decisiones de diseño

## 1. Fusión por posición, no por puntaje

La distancia coseno vive en [0, 2]; `ts_rank_cd` no tiene tope y depende de la
longitud del documento y de la densidad de los términos. Normalizar los dos a una
escala común exige elegir mínimos y máximos que cambian con cada consulta, y una
suma ponderada de puntajes incomparables produce un orden que nadie puede
explicar.

**Reciprocal Rank Fusion** combina posiciones: cada resultado aporta
`1 / (k + posición)`. No hay nada que calibrar, el `k` amortigua las diferencias
entre los primeros puestos, y un documento que sale bien en dos caminos le gana a
uno que sale muy bien en uno solo — que es exactamente lo que se quiere de una
fusión.

`k = 60`, el mismo constante que usa el curso, de Cormack et al. Un `k` grande
achata la curva y obliga a rankear bien en varias ramas; uno chico deja que un
solo primer puesto domine.

**Sin pesos por rama.** La primera versión de esta propuesta los tenía; el curso
deliberadamente no. Y tiene razón: el punto de RRF es que el consenso posicional
decida, y un peso por rama reintroduce exactamente la calibración manual que RRF
evita — con el agravante de que un peso mal elegido es invisible, porque el orden
resultante sigue pareciendo razonable.

**Alternativa descartada:** normalizar por min-max sobre el conjunto devuelto.
Es sensible a un outlier y hace que el puntaje de un resultado dependa de con
quiénes salió, no de cuán relevante es.

## 2. El camino exacto es un camino aparte, no un peso más

`CAC011`, `premium_mo`, `nReceipt`, `10208`: la tokenización del full-text los
destroza (parte por el guion bajo, stemea, y descarta lo que parece stopword) y
el embedding no los ve. Tratarlos con los mismos dos caminos y esperar que
aparezcan es lo que hoy falla.

El camino exacto pregunta por lo que realmente son: `document_id` (`CAC011` es un
código de transacción), `field` (un nombre de campo), o coincidencia literal en
el texto. Es una consulta barata y precisa, y **cuando acierta debería dominar la
fusión**: quien escribe `CAC011` no está preguntando por algo parecido.

Se dispara solo cuando la consulta tiene forma de identificador. Correrlo siempre
sería trabajo inútil en las preguntas en lenguaje natural, que son la mayoría.

## 3. El léxico usa OR ponderado, no AND

`plainto_tsquery` combina todo con `AND`, y por eso `codigo de error 10208`
devuelve cero aunque `10208` esté en el corpus. Con `OR`, cada término aporta y
`ts_rank_cd` se encarga de que el chunk que tiene más términos rankee más alto —
que es el comportamiento que se espera de una búsqueda.

`OR` trae más candidatos, incluidos malos. No importa: la fusión los ordena, y un
candidato mal rankeado que la fusión hunde es mucho mejor que un resultado
correcto que nunca aparece.

## 4. La diversidad es un parámetro, no una regla

Medido: el documento dominante se lleva 4,5 de 10 hits en promedio. En
*"cómo se emite una póliza nueva"* eso es un defecto —7 de 10 vienen de
`CA001k`, que es la solicitud de clave, no la transacción principal—. En
*"qué pasa si el importe de ajuste supera la comisión neta"* los 10 vienen de
`AGL009` y **es la respuesta correcta**: la pregunta es sobre la lógica de ese
proceso.

Forzar diversidad rompería el segundo caso para arreglar el primero. Se expone
como tope de chunks por documento, con un default que no recorta, y queda medido
qué le hace a la métrica.

## 4b. El tope por documento necesita candidatos de sobra

El tope se descubrió a medias. `cap=1` deja un chunk por documento, así que la
respuesta **no puede tener más documentos distintos que los que haya en la lista
de candidatos**. Con `branch_limit = 30`, 30 chunks concentrados colapsan a 6
documentos y una consulta de `k = 10` devuelve 6 resultados con 4 puestos
vacíos.

No es que el relleno esté roto: `cap_per_group` recorre la lista entera. Es que
no queda nada con qué rellenar.

Medido sobre las 26 preguntas escritas por una persona, con `cap = 1` y `k = 10`
[VERIFICADO-CORPUS]:

| `branch_limit` | p@10 | encontró | devolvieron < 10 resultados |
|---:|---:|---:|---:|
| 30 | 0,138 | 85% | **7 de 26** |
| 100 | 0,146 | 88% | 0 de 26 |
| 300 | 0,146 | 88% | 0 de 26 |

100 es donde para la truncación y 300 no compra nada, así que el default queda
en 100.

La latencia es **empate**: 389-430 ms con 30 contra 411-606 ms con 100, una
diferencia menor que la varianza entre corridas. Una primera medición dio 100
más *rápido* que 30 (404 contra 647 ms); era un artefacto de arranque en frío,
porque 30 corrió primero y pagó el calentamiento. Repetida en los dos órdenes,
la ventaja desaparece.

Sobre las 56 preguntas del golden set, `vector+exact cap1` pasó de p@10 0,170 a
**0,177** y de 91% a **93%** de hallazgo.

## 4c. Rango y recall son dos fallas distintas, y solo una la arregla un reranker

Con 35 preguntas escritas por una persona sobre los cuatro módulos del foco hay
material para separar algo que se venía mezclando. De los **85 pares
pregunta-documento**, buscando en un candidato de 60 [VERIFICADO-CORPUS]:

| | pares | |
|---|---:|---|
| ya en el top-10 | 49 (58%) | nada que hacer |
| **rango**: puesto 11 a 60 | 21 (25%) | un reranker los rescata |
| **recall**: afuera del top-60 | 15 (18%) | un reranker **no puede** |

Reordenar no trae lo que no vino. Los dos tercios que un reranker arregla y el
tercio que no son conjuntos **disjuntos**, así que hacen falta dos arreglos y no
uno mejor.

### Las preguntas simples ya están resueltas

El desglose por tipo de pregunta es más nítido que el total:

| | top-10 | rango | recall |
|---|---:|---:|---:|
| pregunta simple (1 documento) | 12 | 2 | **0** |
| pregunta compuesta (3+) | 37 | 19 | 15 |

**Las 15 fallas de recall son todas de preguntas compuestas. Cero en simples.**
12 de 14 pares simples entran al top-10.

### Y el documento que falta no es el problema

Diez de los documentos que faltan en una pregunta compuesta son **la respuesta
anotada de una pregunta simple**: `CA003`, `CA908`, `CO001`, `CO501`, `COL001`,
`COL003`, `COL005`, `COL502`, `COL520`, `SI012`.

`CA003` sale en el **puesto 1** de la pregunta sobre dígitos de la CBU y está
**afuera del top-60** de la compuesta de domiciliación PAC/TRANSBANK, que lo
tiene anotado como relevante. `CA025` y `CO001` salen 1º y 3º solos, y
desaparecen juntos en la compuesta de conversión de propuesta.

El documento es recuperable. **La consulta compuesta es lo que lo entierra**, y
eso es descomposición de consulta, no reordenamiento.

### Lo que esto corrige

La descomposición se había medido antes sobre 5 preguntas, dio 1/5 → 2/5 y por
eso quedó postergada frente al reranker. Con 35 preguntas la lectura cambia: el
reranker sigue siendo el que más pares mueve (21), pero es **estructuralmente
incapaz** de tocar los 15 que ni aparecen, y esos 15 son exactamente los que la
descomposición ataca. La prioridad no es una lista ordenada: son dos trabajos
para dos mitades distintas del problema.

## 5. Dos métricas, y cada una para lo que sirve

Sin número, "mejoró la recuperación" es una opinión. Pero un solo número mal
elegido es peor, porque parece una respuesta.

**`precision@k` sobre un golden set anotado a mano** es lo que se reporta. Es lo
que hace el curso (`scripts/eval_retrieval_s10.py`: `hits / k`, por configuración
con nombre, más latencia) y mide lo que importa: de los k que van a entrar al
contexto del generador, cuántos sirven. Necesita varios documentos relevantes por
pregunta, y por eso hay que anotarlos.

El golden set del curso además incluye **distractores deliberados** —documentos
parecidos pero irrelevantes— para atacar los fallos concretos que enumera. Ese
detalle no es decorativo: un golden set sin distractores mide si el sistema
encuentra, no si sabe descartar.

**La tasa de acierto sobre títulos únicos** es el atajo para iterar. Corre en
segundos, no necesita anotación, y sirve para ver si un ajuste de la fusión mejora
o empeora. Sus límites, escritos y no implícitos:

- Un título no es una pregunta. Premia parecerse al título, así que un cambio que
  ayude a los títulos y no a las preguntas se vería como una mejora.
- Su techo no es 100%: 349 documentos comparten título con otro, por eso se usan
  solo los 1.871 únicos.
- Un "fallo" puede ser correcto: `VIC014_k` → `SGC001_k`, y los dos tienen el
  título *idéntico*.

El proxy nunca se reporta como calidad del sistema. Sirve para comparar dos
versiones del mismo sistema mientras se lo construye.

## 5b. El golden set se borradorea, no se inventa

Las preguntas salen de secciones reales del corpus, y quedan **pendientes de
revisión** por alguien que conozca el negocio antes de reportar cualquier número
contra ellas.

Un golden set escrito por el mismo sistema que después se evalúa contra él no mide
nada: mide si el sistema coincide consigo mismo. Que el borrador venga del corpus
y no de la imaginación ayuda, pero no alcanza — hace falta que alguien diga "esta
pregunta la haría un usuario" y "este documento es el que la responde".

## 6. `GET` y no `POST` para la búsqueda

Una búsqueda es idempotente y sin efectos, y como `GET` es cacheable, enlazable y
se prueba desde la barra del navegador. El corpus está en español, así que la
consulta va URL-encodeada; no es razón para volverla `POST`.

Si algún día la consulta lleva un cuerpo grande —un documento entero como
consulta, por ejemplo— eso es otro endpoint, no este con otro verbo.

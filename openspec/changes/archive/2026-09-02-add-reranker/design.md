# Decisiones de diseño

## 1. El reranker ve 60, no 10

Reordenar los mismos 10 que la búsqueda ya eligió no tiene con qué trabajar. Los
28 pares convertibles están **entre el puesto 11 y el 60** por definición, así
que `retrieve()` con reranker pide el candidato ancho, reordena, y recorta a
`limit` después.

60 no es un número redondo elegido al azar: es el ancho con el que se definieron
"problema de rango" y "problema de recall" al medir, así que moverlo cambia lo
que esas palabras significan en los reportes.

## 2. No hay garantía de no-regresión, y no puede haberla

La descomposición podía prometer cero regresiones porque **agrega** al final de
una lista. Un reranker no: hay 10 puestos y promover uno baja a otro. Es de suma
cero.

Medido, el de modelo rescata 15-16 pares y rompe 6-7. Se intentó protegerlo y no
funciona:

- **Fusionar por RRF el orden base con el del modelo** da un resultado
  **idéntico** a concatenar. Con hasta 10 elegidos, el peor elegido puntúa
  `1/70 + 1/110 = 0,023` y el mejor no elegido `1/61 = 0,016`: todo lo elegido le
  gana a todo lo no elegido. RRF no protege nada acá.
- **Contar el ranking del modelo dos veces** tampoco cambia el resultado, por lo
  mismo.

Así que el daño se reduce por otro lado: dándole al modelo el dato de dominio que
le faltaba. Ver §4.

## 3. Lo que el modelo no elige va detrás, nunca se descarta

`rerank()` devuelve **todos** los candidatos, reordenados. El recorte a `limit`
es del llamador.

Si el reranker filtrara, un candidato perdido ahí no volvería nunca, y el modelo
devuelve menos de 10 ids en 25 de 35 consultas. Filtrar convertiría eso en un
top-10 de 6 resultados.

## 4. El sufijo `_k` en el prompt

Los tres documentos que el reranker empujaba afuera del top-10 eran `DP003_k`,
`CA001k` y `CA001k`. Los tres con sufijo `_k`.

No es casualidad: el modelo lee *"Solicitud de clave para el tratamiento de
pólizas"* y ve un formulario. En esta arquitectura es el **punto de acceso** a la
funcionalidad y lleva la descripción funcional completa: `CA001k` tiene 338
chunks y `CA001A`, titulado "Tratamiento de pólizas", tiene 4.

Decírselo bajó las roturas de 10-11 pares a 5-7.

**Por qué esto no es filtrar la respuesta:** la frase dice qué significa un
sufijo en la arquitectura, no qué documento responde qué pregunta. Es lo mismo
que ya está escrito en `openspec/domain/visualtime-window-types.md`, y salió del
export de `WINDOWS`, no del golden set. Un usuario nuevo del sistema recibiría
esa misma explicación en su inducción.

## 5. Modelo barato, y el número que lo justifica

`gpt-4o` y `gpt-4o-mini` sacaron **el mismo +11** en la corrida donde se
compararon, a 5,6 s contra 3,3 s. El único punto a favor del grande fue 0 ids
inventados contra 1, y el filtro ya descarta los inventados.

El cuello de botella no es la capacidad del modelo. Es que devuelve menos ids de
los que podría y que le falta contexto de dominio, y lo segundo se arregló
gratis.

## 6. Alucinaciones: se descartan y se cuentan

Un id que no estaba en la lista de candidatos es una alucinación. Medido: 1 en 35
consultas con `gpt-4o-mini`, 0 con `gpt-4o`. Poco, pero no cero.

Se descarta y se loguea. Confiarle en silencio sería devolver al usuario un
documento que la búsqueda nunca encontró, con la procedencia inventada.

## 7. Un reranker que falla no se lleva la consulta puesta

Si la llamada al modelo levanta —503, timeout, JSON roto— `rerank()` devuelve los
candidatos como llegaron y loguea el fallo. El orden fusionado es una respuesta
real, solo peor ordenada; propagar la excepción convertiría un 0,140 en un error.

Lo mismo en `get_reranker()`: sin clave devuelve el `LexicalReranker` en lugar de
fallar. `get_embedder()` sí falla, y la diferencia es real: sin vectores no hay
búsqueda, mientras que sin reranker hay una búsqueda medida en 0,140.

## 8. `temperature=0` no es determinismo

Tres corridas idénticas: 57, 58 y 59 pares en el top-10, con `p@10` entre 0,163 y
0,169.

Por eso el número se reporta como rango. Elegir la mejor corrida y publicarla
sería sobreajustar a ruido — el mismo error que evitar al no hacer búsqueda de
grilla sobre los pesos del léxico con 35 preguntas.

## 9. Lo que queda afuera

Los 8 pares perdidos siguen perdidos: **un reranker no los puede tocar**. Están
afuera del candidato de 60 y reordenar no trae lo que no vino. Van por expansión
del grafo de `process_map_edges`, que ya se midió que en cobranzas lleva 9/18 a
14/18.

Y quedan 17 pares en problema de rango que el reranker no convirtió. El oráculo
dice que son alcanzables. Ahí el camino es un cross-encoder entrenado o más
contexto por candidato —hoy son 300 caracteres— y ninguna de las dos se midió
todavía.

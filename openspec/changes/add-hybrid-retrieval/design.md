# Decisiones de diseño

## 1. Fusión por posición, no por puntaje

La distancia coseno vive en [0, 2]; `ts_rank_cd` no tiene tope y depende de la
longitud del documento y de la densidad de los términos. Normalizar los dos a una
escala común exige elegir mínimos y máximos que cambian con cada consulta, y una
suma ponderada de puntajes incomparables produce un orden que nadie puede
explicar.

**Reciprocal Rank Fusion** combina posiciones: cada resultado aporta
`peso / (k + posición)`. No hay nada que calibrar, el `k` amortigua las
diferencias entre los primeros puestos, y un documento que sale bien en dos
caminos le gana a uno que sale muy bien en uno solo — que es exactamente lo que
se quiere de una fusión.

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

## 5. La métrica antes que la mejora

Sin número, "mejoró la recuperación" es una opinión. La línea base ya está
tomada (recall@1 70%, @5 88%, @10 92% con el vector solo), y el script de
evaluación se escribe **antes** de tocar la búsqueda, para que cada decisión de
fusión se contraste en lugar de argumentarse.

**Los límites de la métrica quedan escritos, no implícitos:**

- Un título no es una pregunta. La métrica premia parecerse al título, así que un
  cambio que ayude a los títulos y no a las preguntas se vería como una mejora.
- Su techo no es 100%: hay 349 documentos cuyo título comparten con otro, por eso
  se usan solo los 1.871 únicos.
- Un "fallo" puede ser correcto. `VIC014_k` → `SGC001_k` cuenta como error, y los
  dos documentos tienen el título *idéntico*.

Sirve para comparar dos versiones del mismo sistema. No para afirmar que el
sistema es bueno.

## 6. `GET` y no `POST` para la búsqueda

Una búsqueda es idempotente y sin efectos, y como `GET` es cacheable, enlazable y
se prueba desde la barra del navegador. El corpus está en español, así que la
consulta va URL-encodeada; no es razón para volverla `POST`.

Si algún día la consulta lleva un cuerpo grande —un documento entero como
consulta, por ejemplo— eso es otro endpoint, no este con otro verbo.

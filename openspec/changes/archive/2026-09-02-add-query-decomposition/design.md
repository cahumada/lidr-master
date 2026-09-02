# Decisiones de diseño

## 1. Agregar, no reordenar

Es la decisión que define el cambio y salió de medir, no de razonar.

Las dos variantes que reordenan rompen documentos que la consulta completa ya
encontraba. Fusionar solo las subconsultas da empate exacto —rescata 7, rompe 7—
y agregar la consulta completa como una rama más lo mejora pero sigue rompiendo
4.

La causa es que RRF **diluye**. Un documento en el puesto 3 de la consulta
completa y ausente de las tres partes puntúa `1/63`. Uno en el puesto 20 de la
completa y en el 5 de dos partes puntúa `1/80 + 1/65 + 1/65`, que es más. El
segundo le pasa al primero, y el primero era correcto.

Agregar sin reordenar no tiene ese problema por construcción: el prefijo del
candidato es exactamente el de la consulta completa, y las subconsultas solo
aportan lo que no estaba, debajo.

**La consecuencia hay que decirla:** `precision@10` no se mueve. Este cambio no
mejora lo que el usuario ve hoy. Mejora lo que un reranker puede llegar a ver, y
sin reranker su efecto es cero en la métrica que se reporta.

## 2. El contexto se reparte, no se descarta

Una pregunta compuesta típica tiene la forma:

    Si un recibo tiene configurada una vía de cobro automática como PAC o
    TRANSBANK, ¿cómo se gestiona esta domiciliación bancaria, de qué manera
    afecta a la generación manual de su boletín de cobro y qué controles
    existen si necesito traspasar ese pago a otro recibo?

Todo lo que va antes del `¿` es contexto y **lleva las entidades**: `PAC`,
`TRANSBANK`, "recibo", "vía de cobro automática". La cláusula suelta *"de qué
manera afecta a la generación manual de su boletín de cobro"* no menciona
ninguna de las tres.

Así que cada subconsulta se arma como `contexto + cláusula`. Descartar el
contexto convertiría las subconsultas en preguntas sobre nada.

## 3. Dos formas de coordinación

### Cláusulas coordinadas

Cada parte trae su propio interrogativo. El límite es una coma o una `y`/`e`
**seguida de un interrogativo**:

    ,\s*(?=<INTERROG>)  |  \s+[ye]\s+(?=<INTERROG>)

El lookahead es lo que hace que la regla no parta por cualquier coma. `¿Cuántos
dígitos componen la CBU y qué valores están reservados...?` sí se parte, porque
`y qué` califica.

### Frases nominales coordinadas

Comparten el interrogativo y el verbo:

    ¿Cómo puedo consultar de forma estructurada [los planes definidos para un
    producto], [las exclusiones parametrizadas entre sus coberturas] y [la
    escala de comisiones por año asignada a los intermediarios]?

Acá no hay un interrogativo por parte: hay una **cabeza** compartida (`¿Cómo
puedo consultar de forma estructurada`) y tres frases nominales. El límite es una
coma o una `y` seguida de un **determinante** (`el`, `la`, `los`, `las`, `su`,
`sus`, `un`, `una`, `cada`).

El determinante en cabeza es lo que distingue una frase nominal coordinada de
cualquier enumeración adentro de una sola frase. Sin ese ancla la regla parte
`"pendientes, cheques a fecha"` y produce basura.

La cabeza se recorta hasta el primer determinante del primer segmento, y se
reparte a las tres.

### El orden importa

Se prueba cláusulas primero y frases nominales después. Una pregunta con
cláusulas coordinadas también tiene determinantes adentro, así que la regla
nominal la partiría mal. La de cláusulas es más específica y va primero.

## 4. Por qué reglas y no un modelo

El curso resuelve esto con `query_transform.py` y un LLM, y para el caso general
tiene razón. Acá las reglas alcanzan y traen tres cosas que el modelo no:

- **Deterministas.** El mismo texto da la misma división siempre, así que se
  testea sin red y sin fixtures de respuestas.
- **Sin latencia ni costo.** Una consulta compuesta ya paga 2 o 3 búsquedas; una
  llamada a un modelo antes de eso la encarece por un factor mayor.
- **Auditables.** Cuando una división sale mal se ve por qué, y la regla se
  arregla.

Cubren **20 de las 24 preguntas compuestas**. Las 4 que quedan son enumeraciones
de sustantivos sin determinante:

    ¿Qué secuencia de ventanas, variables de clave inicial y validaciones de
    clientes requiero para realizar la declaración formal de un siniestro?

`variables de clave inicial` y `validaciones de clientes` son plurales
escuetos. Anclarse en algo que no sea un determinante hace que la regla parta
enumeraciones que no debe. **Ahí es donde un modelo gana**, y queda anotado con
su número: 4 preguntas, y hay que ver cuántos de los 8 pares de recall que
quedan están en ellas.

La forma para agregarlo ya está: un `Decomposer` Protocol, igual que `Embedder`
tiene `OpenAIEmbedder` y `HashEmbedder`.

## 5. No dividir es una respuesta válida

De las 35 preguntas, 15 quedan intactas y **11 de esas son de un solo
documento**. Eso es correcto, no una falla de cobertura.

La primera variante partía preguntas simples y rompió `U-SI501-reasignar`:
`SI501` se fue del top-10 al puesto 11 y `SI501_k` al 16, en una pregunta que ya
estaba resuelta. Una pregunta simple partida en dos consultas más angostas
recupera peor que la original.

Con `agregar sin reordenar` ese daño ya no es posible, pero la regla igual no
debe partir lo que no es compuesto: cada subconsulta cuesta una búsqueda.

## 6. La descomposición y la rama léxica se pisan, y gana la descomposición

Medido sobre las 35 preguntas humanas [VERIFICADO-CORPUS]:

| config | `recall@60` | perdidos | latencia |
|---|---:|---:|---:|
| `vector+exact cap1` | 82% | 15 | 481 ms |
| `vector+exact cap1 +split` | **91%** | **8** | 1.140 ms |
| `fused cap1` (con léxica) | 86% | 12 | 2.667 ms |
| `fused cap1 +split` | 86% | 12 | 4.000 ms |

Dos cosas que no se esperaban:

**La descomposición le gana a agregar la rama léxica**, y por más de lo que
cuesta: 91% contra 86%, 8 perdidos contra 12, y 2,3 veces más rápida.

**Y sobre `fused` no aporta nada.** Si agregar candidatos solo puede sumar,
`fused cap1 +split` debería perder 8 y no 12. Que pierda los mismos 12 que
`fused cap1` significa que la presencia de la léxica **impide** que la
descomposición rescate 4 de sus 7.

La explicación más probable —y queda como hipótesis, no como mecanismo
verificado— es **desplazamiento**: con `cap=1` y un candidato de 60 puestos, la
rama léxica sobre una pregunta compuesta larga inyecta muchos documentos, y esos
empujan afuera del top-60 a otros. `fused` no es un superconjunto de
`vector+exact`: son 60 documentos distintos.

Por eso el default sigue siendo `vector+exact`, y por eso la descomposición se
mide sobre ese default y no sobre `fused`.

## 7. Cómo se mide

`precision@10` es la métrica equivocada para este cambio y hay que decirlo antes
de reportar el número, no después. Las métricas correctas son:

- **recall del candidato**: cuántos pares pregunta-documento aparecen en el
  candidato de 60. Va de 70/85 a 77/85.
- **alcanzable por un reranker**: cuántos están entre el puesto 11 y el 60. Va
  de 21 a 28.
- **regresiones**: cuántos salieron del top-10. Tiene que ser 0, y lo es por
  construcción.

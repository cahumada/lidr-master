# Decisiones de diseño

## 1. Por qué se mide antes de fijar el default, otra vez

Cada constante de este pipeline —`DEFAULT_BRANCH_LIMIT`,
`DEFAULT_RERANK_CANDIDATES`, el `cap` por documento— se fijó midiendo, nunca a
ojo. Acá el patrón se repite pero con un resultado distinto: la medición dijo
que NO. Vale documentarlo con el mismo cuidado que un resultado positivo,
porque es la evidencia de que el proceso funciona incluso cuando la hipótesis
inicial estaba mal.

## 2. La democión es SUAVE (multiplicativa), no un filtro — y aun así perdió

Se descartó desde el diseño un filtro duro (excluir `document_kind='index'`
por completo) precisamente porque `SI001_A` y `DP003_A` son documentos índice
que SON la respuesta correcta a dos preguntas reales. Un multiplicador
(`score *= penalty`) deja que un candidato índice siga pudiendo ganar si es la
única evidencia que hay — verificado con
`test_an_index_candidate_can_still_win_if_nothing_else_matches`.

Pero "suave" no bastó: incluso el penalty más débil probado (0,5) hunde a
`DP003_A` del puesto 5 al 39. La razón es aritmética y no de diseño: RRF suma
`1/(k+posición)` por rama, y `DP003_A` gana su puesto 5 con **una sola** rama
vectorial fuerte — no tiene margen para absorber ningún descuento. Un
documento que depende de un solo pilar fuerte no tolera que ese pilar se
debilite, sin importar cuán suave sea el debilitamiento.

## 3. El dedup por texto resolvió el síntoma equivocado

El diagnóstico (`REINSURANCE_INTRO`/`REINSURANCE_REPORTS_INTRO`) parecía un
caso limpio de "misma oración, dos ids, desperdicio de lugares". Y lo es,
**para esa pregunta puntual**. Pero medido contra 85 pares reales, el mismo
mecanismo rompió `CAC1005B`→`CAC1005A` y `CAC1006`→`CAC1006B`: pares
anotados por una persona con un `document_id` específico, no con "cualquier
hermano sirve".

La distinción que el dedup no hace y necesitaría hacer: **texto idéntico no
implica intercambiabilidad para quien pregunta**. `evals/golden_curated.json`
ya tiene una nota reconociendo que `CAC1005`/`A`/`B` son casi
intercambiables — pero "casi" no es "siempre", y un dedup que colapsa
silenciosamente pierde exactamente la distinción que la anotación humana
preserva a propósito.

## 4. Por qué el código se queda apagado y no se revierte

Tres razones, y ninguna es "por si acaso":

- **`document_kind` en la API es valor real e independiente.** El propósito
  documentado de `/search` es *"todo lo necesario para VERIFICAR la
  respuesta"* — saber si un hit es navegación o contenido es exactamente esa
  clase de dato, y no depende de si el ranking lo usa.
- **Los 12 tests fijan comportamiento correcto, no comportamiento deseado.**
  Prueban que `_demote_index_kind`/`_dedupe_by_text` hacen lo que dicen que
  hacen. Eso sigue siendo cierto aunque la conclusión sea "no lo actives".
- **Revertir sería thrash.** El código no tiene ningún costo en producción
  con los parámetros en su default (`index_penalty=1.0` es un no-op
  verificado por test; `dedupe_text=False` no ejecuta nada). Sacarlo y
  tenerlo que rehacer el día que alguien mida un diseño distinto —democión
  condicionada a la competencia real, o fusión de hermanos en vez de
  descarte— es trabajo repetido sin ninguna ganancia hoy.

## 5. Lo que un diseño futuro necesitaría medir distinto

No se implementa ahora — son direcciones, no un plan comprometido:

- **Democión condicionada**: solo aplicar el penalty cuando el candidato
  índice compite contra al menos N candidatos de contenido con score
  comparable, no cuando es la mejor evidencia disponible.
- **Fusión en vez de descarte**: cuando dos candidatos comparten cuerpo
  normalizado, combinar sus `branches`/`ranks` en un solo resultado que
  declare los DOS `document_id`, en vez de que uno desaparezca. Requeriría
  cambiar la forma de `RetrievedChunk` (hoy un solo `document_id` por
  resultado) y no es un cambio chico.

Cualquiera de los dos necesita el mismo barrido contra las 35 preguntas antes
de convertirse en default — la lección de este cambio no es "no se puede",
es "esta forma específica no sirve".

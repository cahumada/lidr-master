# Evaluación de generación — fidelidad de citas

> Si la terminología de recuperación no te dice nada, empezá por
> [COMO_LEER.md](COMO_LEER.md). Esta página mide **otra cosa**: no si el
> buscador encontró el documento, sino si la respuesta generada *cita* un
> documento que se puede verificar.

## Qué se mide, y por qué no es `precision@k`

`precision@k` pregunta *de los k chunks que van al contexto, cuántos
sirven*. La generación pregunta *de las citas que salen con la respuesta,
cuántas se pueden contrastar con lo recuperado, y si el documento que una
persona anotó está entre ellas*.

Tres números, cada uno por una razón distinta:

| métrica | pregunta que responde | de dónde sale |
|---|---|---|
| `citation_coverage` | ¿Las `citations` de la respuesta incluyen un `document_id` que el golden set marca como relevante? | Los `SearchHit` que adjuntó `POST /answer`. **No** los marcadores `[CA014 · …]` de la prosa. |
| `grounded_rate` | ¿La prosa inventó un `document_id` que no estaba en esos hits? | El guardrail de salida (`check_grounding`). |
| `inline_hit` | ¿La prosa misma nombró un documento esperado? | Regex sobre el texto generado. Informativo: el contrato verificable es `citations`. |

`citation_coverage` es el número que el criterio de aprobación pide: *evals
reales, no pruebas manuales*. Se corre contra
`evals/golden_curated.json` (preguntas escritas por una persona) y, si se
pide, contra `evals/golden_retrieval.json`. Una pregunta sin
`relevant_document_ids` no entra: no hay nada que verificar.

Se cuenta **por pregunta, no por cita**. Una pregunta anotada con
`COL005` está cubierta si `COL005` aparece al menos una vez en
`citations`. Varios chunks del mismo documento no suman.

## Cómo se corre

```bash
cd ai-service
uv run python scripts/eval_generation.py --source curated
uv run python scripts/eval_generation.py --source curated --max-questions 8
uv run python scripts/eval_generation.py --source both --skip-llm --write-report
```

`--skip-llm` mide solo `citation_coverage`. Es legítimo: las `citations`
del endpoint **son** los hits recuperados, y esa es la procedencia
verificable. La corrida con LLM agrega `grounded_rate` e `inline_hit`.

El pipeline es el mismo que `POST /answer`: `vector+exact`, `cap=1`,
descomposición y reranker. No se forkea.

## Lo que estos números NO dicen

**No son la calidad de la prosa.** Una respuesta cubierta y grounded puede
estar mal redactada, incompleta o haber ignorado un chunk útil. Eso pediría
un juez (humano o LLM-as-judge) sobre un conjunto anotado a nivel de
afirmación, que hoy no existe.

**No reemplazan a `RETRIEVAL_EVAL.md`.** Si `citation_coverage` es bajo, el
arreglo está en la recuperación, no en el prompt. Si `citation_coverage`
es alto y `grounded_rate` es bajo, el modelo está inventando marcadores y
el arreglo está en el prompt o en el modelo.

**`inline_hit` puede ser más bajo que `citation_coverage` sin que eso sea
un defecto.** El contrato le dice al llamador que mire `citations`. La
prosa puede responder bien citando un subconjunto, o declarar
insuficiencia.

## Resultados

Corrida 2026-09-03: `source=curated`, `skip_llm=True`, 35 preguntas humanas,
pipeline `vector+exact` cap=1 +split +rerank. `grounded_rate` e `inline_hit`
no aplican en esta corrida — no hubo prosa. El número que el criterio de
aprobación pide es `citation_coverage`.

| métrica | valor | qué mide |
|---|---:|---|
| `citation_coverage` | **94%** (33/35) | fracción de preguntas cuyo `document_id` esperado aparece en `citations` |
| `grounded_rate` | n/a (`--skip-llm`) | fracción de respuestas sin `document_id` inventado en la prosa |
| `inline_hit` | n/a (`--skip-llm`) | fracción cuya prosa nombra un documento esperado |
| ms/pregunta | 5377 | latencia media de recuperación |

Las dos que no cubren son fallas de **recuperación**, no de generación:

| id | esperado | qué volvió en su lugar |
|---|---|---|
| `U-CO001-unit-linked-documentos` | `CO001` | `CO001_A` (acompañante) y documentos de vida/unit-linked, sin `CO001` |
| `U-multi-conversion-propuesta-primera-prima` | `CA001k`, `CA025`, `CO001` | la cadena de `CAC1006*` y `CO001_A`; ninguno de los tres anotados |

Eso es el mismo tipo de hueco que ya documenta `RETRIEVAL_EVAL.md`: el
documento está en el corpus y a veces en el candidato, pero no en el top-10
que entra al prompt. El generador no puede citar lo que no recibió.

### Muestra con LLM (mismas 5 primeras preguntas)

Corrida 2026-09-03: `source=curated`, `skip_llm=False`, `--max-questions 5`
(COL005, COL003, COL502, COL520, COL001). Completions reales con
`gpt-4o-mini`, temperatura 0.

| métrica | valor |
|---|---:|
| `citation_coverage` | 100% (5/5) |
| `grounded_rate` | 100% (5/5) — ningún `document_id` inventado |
| `inline_hit` | 80% (4/5) — la prosa de COL502 no nombró el código; `citations` sí lo traía |
| ms/pregunta | 8372 |

## Por pregunta

| id | cubrió | grounded | esperado | citations |
|---|---|---|---|---|
| `U-COL005-cuadre` | sí | sí | COL005 | COL005, COL525, OPC001, OPC824, COC001, COC009, COC998, CO001, CO012, COL007 |
| `U-COL003-pendientes` | sí | sí | COL003 | COL003, COL512, COL500, COL520, COL526, AGL857, COL889, COL910, COL742, COL504 |
| `U-COL502-comision-banco` | sí | sí | COL502 | COL502, CO515, COL520, COL520_k, CO004, MCO678, CO009, GIL54538, MA7502, MA0401 |
| `U-COL520-totales-lote` | sí | sí | COL520 | GIL54538, INT54538, COL524, INT54124, COL005, COL887, COL520, CO001_A, COL870, COL502 |
| `U-COL001-historico` | sí | sí | COL001 | COL001, COC001, COL525, COC902, COL868, COC009, COL887, COL504, COL821, AGL005 |
| `U-CO501-desmarcar-rechazo` | sí | sí | CO501 | CO515, CO501, CO514, COL594, CO001_A, COL500, CO009, COL512, COL701, MA5003 |
| `U-multi-lote-pac-rechazos` | sí | sí | CO501, COL500, COL520, COL704 | COL520, GIL54538, COL500, COL502, CO501, COL704, COL520_k, CO515, COL836, COL701 |
| `U-multi-rechazo-cuenta-corriente` | sí | sí | CO501, COL005, COL502 | CO501, INT54538, CO515, COL836, COL010, INT54134, COL504, COL895, INSROUTINEANNULMENT, MCO508 |
| `U-multi-cartera-pendientes` | sí | sí | COL003, COL007, COL500 | COL500, COL512, COL003, COL007, COL525, COL836, COL1162, COL910, COL821, INT54132 |
| `U-multi-desmarcar-y-repaso` | sí | sí | CO501, COL001, COL500 | CO005, CO501, CO515, COL594, COL500, CO009, COL701, COL504, CAL516, MA0019 |
| `U-multi-financiamiento-cuotas` | sí | sí | CO501, COL500, COL502, COL520, COL704 | COL500, COL906, COL836, CA017A, COL556, CO001_A, CO004_k, CO009, COL512, COL520 |
| `U-CA051-plantilla-excel` | sí | sí | CA051 | CAL013, CA051, CAL013_K, SIL501, CO510_k, CAC001, SIL005, CO633A, CAC011, VIL7700 |
| `U-CAL006-formulas-reservas` | sí | sí | CAL006 | MGSL002, CAL514, CAL006, CR302, INSCALRESERAXS, INSCALRESERAS, INSCAL_RESSFPRS, INSCAL_RESSFPRM, INSCALRESERFPR, CRL007 |
| `U-CA022-clausula-duplicada` | sí | sí | CA022 | CA022, VI811, SI001_k, ST015, DP018G_K, VI681, CA500, DP029_K, SI629, CR766_k |
| `U-multi-policy-his-movimientos` | sí | sí | CA001k, CA034, CA035, CAL400 | GIL103, AGL728, GIL101, GIL102, CA001k, CA034, CA033, CAL400, CO633A, GIL111 |
| `U-multi-propuesta-a-poliza` | sí | sí | CA001k, CAC1005, CAC1005A, CAC1005B, CAC910 | VIL7701, CAC910, CAC959, CAC1005A, CAC1005B, CAC1006, CAC1006A, CAC1006B, POLICIES_GENERAL, CA001k |
| `U-multi-primera-prima-y-caja` | sí | sí | CA001k, CA003, CAC1006, CAC1006A, CAC1006B | GIL004, CAC862, CAC1006B, CAC1006A, CAC1006, CO001_A, MA0182, BC013, CO004, CA003 |
| `U-SI501-reasignar` | sí | sí | SI501, SI501_k | SI501, SI501_k, SIC500, SIL006, SIL1071, SI004, SI007, SIL1069, SIL1070, CRL002 |
| `U-CA908-jerarquia-productores` | sí | sí | CA908 | CA908, CA024, AG001, ST010, POLICIES_GENERAL, CA025, CA001k, AGL008, MAG901, CA401 |
| `U-SI012-recobro` | sí | sí | SI012 | SI012, MA00192, SI013, MA0216, CRL007, CRL008, CR008b, CRL010, SI006, GE099 |
| `U-multi-declaracion-siniestro` | sí | sí | SI001_A, SI001_k, SI004 | SI001_k, MSI001, CLAIMS-ASPECTOSGENERALES, SI004, SI001_A, DP056, SI008_k, SI010_k, SIL006, OS001 |
| `U-multi-pago-siniestro` | sí | sí | SI008, SI008_k, SI777 | SI777, SI008_k, GIL008, SI008, SIL501, OP006, OP503_k, OP714, OP503, CLAIMS-INTRO |
| `U-multi-consulta-siniestros` | sí | sí | SIC001, SIC002, SIL00970 | CLAIMS-INDEX, SIC001, SIL1067, SIL1072, SIL1075, CAC950, SIL00970, SIL001, SIL1065, SIL1070 |
| `U-multi-coberturas-individual-vs-matriz` | sí | sí | CA001k, CA014, CA014A | CA014A, VI666, CA014, CA001k, CA001M, CA022A, CA022, CA006, CA013A, CAL683 |
| `U-multi-traspaso-pago` | sí | sí | CA001M, CA001k, CO634 | CO634, GIL005, COL504, CO001_A, CO008, CO515, COL686, COL507, AGL001, COL890 |
| `U-multi-limites-vida-comisionables` | sí | sí | CA014, CA014A, CA908 | CA014, MVI773, INSGUARANTDS, INSGUARANTDT, INSGUARANTDD, LIFE_AM_C_CAP, INSCALCAP_COLLECT, DP19AP, CA024, MAG002 |
| `U-CA003-cbu-tipo-cuenta` | sí | sí | CA003 | CA003, BC013, CA403, MA0190, MA5633, MA1014, MA0400, MA6023, MA6753, OP090 |
| `U-CO001-unit-linked-documentos` | NO | sí | CO001 | MA5587, CO001_A, VI7000, COL556, COL520, VIL7008, VI7002, VIL7001, VI7003, VI021 |
| `U-DP001-borrar-ramo-comercial` | sí | sí | DP001 | DP001, CAC989, DP110, CAC988, SIL00970, MCO516, VI7000, CAC1024, MSI010, GIL54528 |
| `U-multi-definicion-producto` | sí | sí | DP003, DP003_A, DP003_k | DP003_k, DP003_A, DP002, ST005, MDP001, DP003, MDP001_k, DP033, DP012, DP008 |
| `U-multi-cobertura-vida-instalacion` | sí | sí | DP018G, DP018G_K, DP033 | DP018G_A, DP018G_K, POLICIES_GENERAL, DP033, CA014, DP032, CAC986, CAC1005, SIL780, DP607A |
| `U-multi-consultas-disenador` | sí | sí | DPC925, DPC926, DPC982 | DPC982, DPC926, MAG504, DP029_A, MAL002, DPC925, AGC844, AGC956, ST015, AGC001 |
| `U-multi-conversion-propuesta-primera-prima` | NO | sí | CA001k, CA025, CO001 | VIL7701, GIL004, DP005, CAC1006, CAC1006A, CAC1006B, CAC862, CO001_A, MA0401, GIL005 |
| `U-multi-domiciliacion-pac-transbank` | sí | sí | CA003, CO632, CO632_k, CO634 | COL502, COL500, COL520, CO634, CO501, CO009, COL010, POLICIES_GENERAL, CO632, COL512 |
| `U-multi-colectivo-innominado` | sí | sí | CA003, CA025, CO001 | CA025, COL500, CA403, CA036_A, COL512, CA003, CA036_k, CA006, CAC014, VI811 |

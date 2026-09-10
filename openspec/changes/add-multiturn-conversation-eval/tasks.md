# Implementation Tasks

## 1. El golden set
- [x] 1.1 Secuencias de al menos dos turnos en `evals/`, con la pregunta escrita,
  la reescritura esperada y los `document_id` que la respuesta debería citar.
  `evals/golden_multiturn.json`: **12 secuencias, 25 turnos** (11 de dos turnos
  y una de tres). Un desvío declarado sobre «la reescritura esperada»: se anotan
  los `expected_referents` —hacia dónde apunta la pregunta— y **no el texto
  literal** de la reescritura. El resolver hoy escribe `(sobre CA014)` y ese
  formato es una decisión de implementación: fijarlo en el golden haría que un
  cambio de formato rompiera el eval sin que nada se haya degradado.
  Y `expected_referents` se separa de `relevant_document_ids` porque no son lo
  mismo: en `MT-CA014-matriz` («¿Y para la póliza matriz?») el referente es
  `CA014` y el documento que responde es `CA014A`. Colapsarlos deja sin saber si
  falló el resolver o la recuperación.
- [x] 1.2 Incluir los tres casos que importan: referente claro, referente
  ausente (no debe reescribir) y referente ambiguo. **8 `clear`, 3 `absent`,
  2 `ambiguous`** sobre los 13 turnos posteriores. Los `ambiguous` se reportan
  aparte y no cuentan de ningún lado: contarlos exigiría elegir una de las
  lecturas y después evaluar al resolver contra la propia elección.
  Dos casos que vale la pena nombrar porque no son de manual:
  `MT-OP001-esa-pantalla` mide el precio de una guarda que ya está tomada —el
  resolver descarta `esa|ese|esos` cuando lleva sustantivo detrás, lo que evitó
  3 falsos positivos en el golden de recuperación y a cambio deja pasar éste—, y
  `MT-OP001-reemplazo-de-referente` es la única secuencia que puede fallar
  nombrando un referente que **alguna vez** fue correcto, porque
  `last_document_ids` se reemplaza cada turno y no se acumula.
  Un test guarda la forma del archivo (`tests/evals/test_multiturn_scoring.py`):
  que los dos buckets estén poblados, que ningún primer turno lleve `referent`,
  y que cada etiqueta venga con su `why`. Sin esa guarda, borrar un `referent`
  saca ese turno de la métrica sin que nada avise y el número **mejora por
  haber medido menos**.
- [ ] 1.3 Revisión humana del set antes de reportar cualquier número — la misma
  regla que la spec de `retrieval` fija para el golden de recuperación.
  **Pendiente, y es del dueño del repo.** El archivo está en
  `DRAFT_NOT_REVIEWED` con las dos casillas de `review` en `null` en las 12
  secuencias, y el reporte lo repite arriba de la tabla. Lo que hay que
  confirmar por secuencia son dos cosas: que las preguntas son las que una
  persona escribiría, y —la que hace todo el trabajo— que la etiqueta
  `clear` / `absent` / `ambiguous` es correcta. Esa etiqueta es un juicio
  humano sobre si una pregunta depende de la anterior; hasta que alguien la
  confirme, los números miden el criterio de quien escribió el archivo.

## 2. La medición
- [x] 2.1 Falso negativo del resolver: preguntas con referente real que quedaron
  sin resolver, sobre el total de las que lo tenían. **50% (4 de 8)** en modo
  resolver. Los cuatro son formas de elidir el sujeto que el regex no marca:
  un posesivo (`¿cuáles son sus validaciones?`), el sujeto omitido del todo
  (`¿qué campos tiene?`), un demostrativo con sustantivo (`esa pantalla`) y un
  pronombre de objeto (`¿qué pasa si no la completo?`).
- [x] 2.2 Calidad de la reescritura, no solo su presencia. Tres veredictos y no
  dos: `ok` (todos los referentes nombrados estaban anotados),
  `partial_referent` (nombró el correcto **y además** otro) y `wrong_referent`
  (nombró solo referentes que no eran). `false_negative` y `wrong_referent`
  nunca comparten columna: el primero es el resolver callándose, el segundo es
  hablando y apuntando a otro lado, que es peor porque produce una búsqueda
  equivocada con más confianza que la pregunta rota.
  **Y el tercer paso encontró algo que el segundo habría tapado.** Las dos
  direcciones dan igual en los dos modos —era esperable: el resolver decide con
  un regex sobre el texto, y el texto no cambia porque haya una base atrás—,
  pero la calidad no: **4/4 correctas aisladas y 0/4 por el grafo**, las cuatro
  `partial_referent`. La causa no es el resolver sino lo que recibe: el turno
  anterior cita **diez** documentos, `last_document_ids` los guarda todos y el
  resolver nombra los primeros `MAX_REFERENTS = 2`. Así
  `¿Y qué validaciones tiene?` se busca como `(sobre CA014, CAC1021)` cuando la
  pregunta era por uno solo. Con dos veredictos —reescribió o no— esto salía
  4/4 en los dos modos y no se veía.
- [x] 2.3 Reportar las dos direcciones juntas. Un número solo vuelve a dejar el
  hueco que este change existe para cerrar. El script imprime y el reporte
  tabula las dos sobre **su propio denominador** —los `clear` para el falso
  negativo, los `absent` para el falso positivo— y un bucket vacío devuelve
  `None`, no `0%`: un golden sin `absent` es un golden malo, no un cero de
  falsos positivos.
- [x] 2.4 (nuevo) Delta de spec en `conversation-memory`: el requirement de
  medir las dos direcciones. No corrige nada de lo que la spec afirma —el
  resolver es conservador, como dice— sino que **agrega** la regla de que una
  dirección sola no es un resultado. Ver 4.3.

## 3. El runner
- [x] 3.1 Un eval que corra por el grafo (`/answer/agentic/start` + progreso) y
  no por `generate_answer`, para medir lo que el usuario recibe.
  `scripts/eval_multiturn.py --through-graph`, con el `TestClient` de FastAPI
  sobre la app real: pasa por los routers, los modelos y las dependencias de
  verdad —incluido el guard del token— sin necesitar un proceso levantado ni un
  puerto libre. Dos detalles que salieron de correrlo y no de planearlo:
  1. En Windows hubo que fijar `WindowsSelectorEventLoopPolicy`. El default es
     `ProactorEventLoop` y psycopg se niega a correr en async sobre él, así que
     el pool del checkpointer no terminaba de inicializar, el grafo quedaba no
     disponible y **cada `/answer/agentic/start` contestaba 503**. Limitado al
     script: nada en `app/` fija una política de loop, y bajo uvicorn el loop lo
     elige el servidor.
  2. El modo `resolver` **no** es redundante con éste, y la diferencia es el
     hallazgo. Aislado, el turno recibe un documento anotado; por el grafo el
     turno anterior citó diez, así que la misma reescritura que puntúa `ok`
     aislada nombra un segundo referente que nadie pidió. Reportar solo el
     modo grafo esconde qué pieza arreglar.
  Una corrida que pausa en el gate de revisión humana **no se retoma**: que el
  gate dispare es un resultado legítimo, y aprobarlo desde el script metería el
  criterio del script en un número que mide el del sistema. En la corrida
  completa los 25 turnos terminaron `completed` y ninguno pausó.
  **Lo que el falso negativo cuesta, visto acá y no deducido**: una pregunta sin
  resolver no se queda sin respuesta, se busca tal cual y trae ruido.
  `¿Qué campos tiene?` devolvió `HO001, MGE001, INT54550…`, nada que ver con el
  `CO008` del turno anterior; `¿Qué pasa si no la completo?` devolvió
  `MA0278, MCA005, CA050…` en vez de `CA001M`. El sintetizador después escribe
  una respuesta bien citada sobre eso.
- [x] 3.2 Anotar en el resultado qué anchors se aplicaron y si la memoria
  desplazó evidencia (`dropped_hits`). Tabla «Lo que agregó el grafo» del
  reporte, con estado, documentos citados, anchors en vigor y `dropped_hits`
  por turno. Los tres salen del payload de `/progress`, así que es lo que la
  consola ve, no una instrumentación paralela.
  Dos resultados que hay que leer con cuidado:
  - **Los anchors sí quedan en vigor.** `MT-anchor-prefijo-fijado` reporta
    `transaction_prefix` y su turno 2 —que no nombra el prefijo— devolvió diez
    documentos `CA*`, contra el `CO510, BC968, MCO505…` que devolvió la misma
    pregunta sin anchor en `MT-CA014-posesivo`.
  - **`dropped_hits` fue 0 en los 13 turnos**, así que estas secuencias **no
    ejercitaron** el presupuesto compartido entre memoria y evidencia. No es que
    la memoria nunca desplace evidencia: con dos o tres turnos cortos nunca tuvo
    que elegir. Medirlo pide secuencias más largas y no están acá.
- [x] 3.3 (nuevo) Los dos modos escriben **el mismo archivo sin borrarse**, una
  sección por modo. No es prolijidad: el eval vecino ya pagó la alternativa
  —`eval_retrieval.py` con un solo `--config` sobrescribió la tabla completa de
  cuatro configuraciones y hubo que recuperarla de git—. Y `--max-sequences`,
  para hacer un smoke del modo grafo sin gastar una completion por turno, **no
  escribe reporte**: los mismos títulos de columna con menos turnos detrás se
  leen como una medición completa.

## 5. Lo que esta medición destapó y NO se arregla acá

- [ ] 5.1 **El resolver nombra referentes de más porque la fuente los trae de
  más.** Medido: 0 de 4 reescrituras correctas por el grafo, las cuatro
  `partial_referent`, porque `facts_from_turn` guarda los diez documentos que
  citó el turno anterior y el resolver toma los dos primeros. Arreglarlo es una
  decisión sobre `facts_from_turn` o sobre `MAX_REFERENTS` —por ejemplo, nombrar
  solo el documento del que salió la evidencia que más pesó, en vez de los dos
  primeros de una lista ordenada por ranking— y **no** sobre el regex. Va a su
  propio change, con esta medición como línea de base: hoy 4/4 aislado y 0/4 por
  el grafo, y un arreglo tiene que subir el segundo sin bajar el primero ni
  mover las dos direcciones.
- [ ] 5.2 **Las cuatro formas de elisión que el resolver no marca.** Un
  posesivo (`sus`), el sujeto omitido del todo, un demostrativo con sustantivo
  (`esa pantalla`) y un pronombre de objeto (`la`). Tampoco se arregla acá, y
  hay una razón: la guarda que deja pasar `esa pantalla` es la que evitó 3
  falsos positivos en el golden de recuperación, así que aflojarla mueve las dos
  direcciones a la vez. Cualquier cambio se mide con este eval antes y después.

## 4. Cierre
- [x] 4.1 `uv run pytest` y `uv run ruff check .` en verde desde `ai-service/`.
  Ruff limpio. Y la suite encontró algo que **no es de este change** y hay que
  decirlo: 52 tests de `tests/api/` fallaban con `KeyError` afirmando contra un
  cuerpo de error, porque `add-service-authentication` puso
  `require_service_token` en todos los routers y el guard pasa solo cuando
  `SERVICE_TOKEN` está vacío. Eso volvió la suite dependiente del entorno de
  quien la corre: con un token en el `.env` local —lo que tiene cualquier
  máquina que alguna vez le habló al servicio desplegado— todo da 401. **CI no
  podía verlo**: no define secretos, así que siempre corrió con el guard
  apagado. Arreglado con un fixture `autouse` en `tests/api/conftest.py` que lo
  apaga **explícitamente**, en vez de que esté apagado por casualidad; el guard
  lo sigue cubriendo `test_service_auth.py`, que arma su propia app. Los 116
  tests de `tests/api/` en verde después del arreglo.
  Una nota de método: **una sola suite a la vez**. La primera corrida de esta
  tarea se solapó con un smoke del modo grafo contra el mismo Postgres de
  Railway, y eso agrega fallas que no son del código.
- [x] 4.2 `python scripts/validate_specs.py` sin errores. **0 errores y 0
  advertencias**: la única que había era de este mismo change, que estaba en
  vuelo sin deltas bajo `specs/`.
- [x] 4.3 Actualizar `openspec/specs/conversation-memory/spec.md` solo si la
  medición contradice lo que hoy afirma. **No la contradice**, y por eso el
  delta no corrige: la spec pide que el resolver sea conservador y un 50% de
  falso negativo es perfectamente compatible con serlo. Lo que el delta
  **agrega** es la regla que faltaba —que una dirección sola no es un
  resultado— más el escenario de que la aislación del falso negativo use los
  documentos anotados del turno anterior y no lo que devolvió la recuperación,
  y el de la revisión humana del set. El delta vive en
  `changes/add-multiturn-conversation-eval/specs/conversation-memory/spec.md` y
  se integra al archivar.

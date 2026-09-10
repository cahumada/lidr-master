# Diseño

Cinco decisiones que un lector futuro, si no, preguntaría por qué.

## 1. Se guarda el estado declarado, no un booleano nuestro

El catálogo `TABLE26` dice `1 = Activo`, `2 = En proceso de instalación`,
`3 = Acceso restringido`. Que el sistema **solo contemple el `1`** es
conocimiento del analista funcional (`[TÁCITO]` en el documento de dominio), no
algo que el catálogo declare.

Si la columna guardara `is_current: bool`, el hecho y la interpretación quedarían
colapsados en el mismo lugar, y el día que la regla cambie —o que aparezca otro
valor— no habría forma de saber qué decía el dato original. Peor: una respuesta
que dijera *"esta transacción fue dada de baja"* estaría **inventando**, porque
el catálogo dice "acceso restringido", que no es lo mismo.

Así que la columna guarda el nombre declarado y la regla operativa vive en el
código, en un solo lugar, derivable y cambiable sin migración.

**Alternativa descartada:** guardar el código crudo (`'1'`, `'3'`). Perdió por el
mismo motivo por el que `window_type_name` guarda el nombre y no el `6`: el chunk
se embebe y se muestra para que lo lea un modelo, y `3` no le dice nada a nadie.

## 2. El `4` se normaliza a `3`, pero con warning

Son 18 filas, y que el `4` es un error de datos que se trata como `3` es
`[TÁCITO]` del usuario. Normalizarlo en silencio convertiría un defecto de los
datos en un hecho invisible: si la próxima corrida trae 200, nadie se enteraría.

Por eso la normalización cuenta y loguea. El valor **crudo sigue disponible** en
`visualtime.business_data.row`, que es el mirror inmutable: la normalización es
recuperable.

Un valor que no sea `1`, `2`, `3` ni `4` **no se normaliza a nada**: queda no
resuelto, como cualquier otro campo opcional que el árbol no resuelve.

## 3. La advertencia se renderiza solo cuando hay algo que advertir

`render_hit_block` es el único renderer de un hit, y `fit_to_budget` cuenta
tokens sobre exactamente lo que devuelve. Agregar una línea a **todos** los
bloques tendría dos costos: tokens en cada hit de cada consulta, y —más caro— que
ninguna corrida del eval de fidelidad sea comparable con las anteriores, que es
justo lo que la versión de prompt existe para evitar.

Renderizando la advertencia **solo cuando el estado no es `Activo`**, un hit
vigente o no resuelto sale byte a byte igual que hoy. Las corridas del golden set
que no toquen documentos de transacciones no contempladas siguen siendo
comparables, y las que sí los toquen cambian **porque el resultado cambió**, que
es lo que se quiere medir.

Consecuencia: **no se bumpea `PROMPT_VERSION`.** El template no cambia; cambia el
contexto, y solo para la evidencia que lo merece. La corrida de fidelidad se
vuelve a correr y el antes/después se anota en las tasks.

## 4. El estado va como metadata, no dentro del texto embebido

Meterlo en `text` cambiaría el `content_hash` de los chunks afectados —la clave
física del chunk es `(tenant_id, doc_version, source_type, content_hash)`— y
obligaría a re-embeber. Como metadata, el backfill es un `UPDATE`: la spec de
`chunk-schema` ya declara que una carga que encuentra el mismo hash **actualiza
las columnas de metadata y no la identidad**, así que este campo entra por el
camino que ya está previsto.

El modelo igual lo lee, porque `render_hit_block` lo pone en el prompt. La
diferencia es que no se paga un re-embedding de 56.537 chunks para decir algo que
el contexto puede decir en una línea.

**Alternativa descartada:** un rebuild completo del corpus. Funciona, pero cuesta
tokens de embedding y una ventana de corrida para lograr exactamente el mismo
resultado que un `UPDATE` de segundos.

## 5. El árbol se puede armar desde dos fuentes, y el setting decide

`FunctionalSpecChunker` recibe un `NavigationTree` ya construido y **no habla con
la base**: eso es lo que lo mantiene agnóstico del framework y testeable sin
Postgres. Esa frontera no se toca.

Lo que se agrega es un **segundo loader**, que arma el mismo objeto desde
`visualtime.business_data` en lugar del CSV. El árbol sigue siendo un objeto de
valor; de dónde salieron sus filas es un detalle del composition root
(`dependencies.py`).

Cuál gana lo dice un setting explícito, con el mismo patrón que ya usa el corpus
(*"`CORPUS_BUCKET` es lo que decide cuál de las dos fuentes se usa"*):
`BUSINESS_DB_RUN_ID` puesto → gana el mirror; vacío → el CSV, y el estado queda
no resuelto en todos los códigos.

Y la corrida **se nombra**, no se descubre: leer "la más reciente" haría que el
árbol cambie sin que nadie lo decida, que es exactamente lo que
`CorpusVersionRow` evita para el corpus con su índice de "una sola activa".

**Alternativa descartada:** agregarle una sexta columna al CSV. El CSV se genera
a mano, `navigation.py` lo lee por posición y el mirror ya tiene el dato con su
procedencia (`run_id`, `manifest_sha256`). Sumar una columna sería mantener dos
caminos para el mismo dato, y el artesanal es el que no se puede auditar.

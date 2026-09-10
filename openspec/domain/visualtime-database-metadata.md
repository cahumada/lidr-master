# Dominio: la metadata de la base de VisualTIME

Reference knowledge about the SOURCE system's database, not about this service.
Nothing here is a requirement on our code — see `openspec/specs/` for that.

|| Conocimiento de referencia sobre la base del sistema FUENTE, no sobre este
servicio. Nada de acá es un requerimiento sobre nuestro código.

**Aportado por:** el usuario (analista funcional del sistema), 2026-09-08 y
2026-09-09, con el extractor `dw-oracle-extractor` y mediciones sobre la
réplica en Postgres.

Complementa [visualtime-navigation-taxonomy.md](visualtime-navigation-taxonomy.md)
y [visualtime-window-types.md](visualtime-window-types.md): aquellas describen el
árbol de menú y los tipos de ventana; ésta describe **qué más declara la base**,
**qué se puede y qué no se puede vincular** con el corpus documental, y **cómo
hay que leerla**.

Estados de evidencia: `[VALIDADO-BD]`, `[TÁCITO]`, `[HIPÓTESIS]`,
`[VERIFICADO-CORPUS]`. Nunca colapsar una hipótesis en un hecho.

**Toda medición de este documento sale de una sola corrida**, para que los
números sean comparables entre sí:

| | |
|---|---|
| `run_id` | `20260909_214921` |
| `tenant` / `env` | `life_seguros` / `PROD` |
| extractor | `1.0.0`, snapshot del 2026-09-09 22:47 UTC |
| corpus contrastado | `doc_version = DW Funtionals 2026.1`, 56.537 chunks, 2.176 documentos |

---

## 1. El insumo: cómo llega `[VALIDADO-BD]`

`dw-oracle-extractor` (repo aparte, Node/TypeScript) extrae de Oracle y carga en
**PostgreSQL, esquema `visualtime`**, en la misma instancia donde vive el vector
store. Cuatro tablas:

| tabla | contenido en esta corrida |
|---|---|
| `extraction_runs` | una fila por corrida: `run_id`, `manifest`, `manifest_sha256`, `config_fingerprint`, `extractor_version`, `created_at_utc`, `loaded_metadata`, `loaded_dependencies`, `loaded_data` |
| `business_tables` | **2.411** tablas con `description_es`/`description_en` y `columns`/`constraints`/`indexes`/`triggers`/`sequences` como `jsonb` |
| `business_dependencies` | **91.025** aristas entre objetos, 12.158 orígenes y 8.133 destinos |
| `business_data` | **201.751 filas de 753 tablas** — el contenido de las tablas de la allowlist, una fila por fila fuente (`pk text[]` + `row jsonb`) |

El JSONL del snapshot queda en el blob con su hash: es la evidencia inmutable, y
Postgres es la copia consultable, reconstruible desde ahí.

Lo que **no** está: el código fuente de las rutinas queda como archivos `.sql`
del snapshot, sin cargar a Postgres.

## 2. Contrato de lectura: toda consulta pasa por la corrida vigente `[VALIDADO-BD]`

Las tablas de datos son únicas por `(tenant, env, owner, name)` —o por la tupla
de la dependencia, o por `(owner, table_name, pk)`— y los loaders hacen **upsert,
nunca delete**. De ahí tres consecuencias:

1. `run_id` significa **la última corrida que escribió esa fila**, no la corrida
   a la que la fila pertenece. No hay historia: no se puede reconstruir un
   snapshot anterior desde estas tablas.
2. Un objeto borrado en Oracle **sobrevive** en la réplica con un `run_id` viejo.
   Leer sin filtrar por corrida es responder sobre objetos que ya no existen.
3. Las filas de corridas anteriores **se cuentan y se reportan**, nunca se
   ignoran en silencio.

Además:

- **La corrida vigente se elige explícitamente** entre las de `extraction_runs`
  — decisión del dueño del repo, 2026-09-08. No es "gana la más reciente", por
  la misma razón por la que activar una versión del corpus es explícito
  (`CorpusVersionRow`: una versión a medias no debe poder activarse sola).
- Hay que exigir **la bandera del comando**, no el `status`: `loaded_metadata`
  para el diccionario, `loaded_dependencies` para el grafo, `loaded_data` para el
  contenido. Las tres cargas son independientes y `status` arranca en `partial`.
- `created_at_utc` (cuándo se fotografió Oracle) manda sobre `loaded_at` (cuándo
  se cargó la foto). Recargar un snapshot viejo actualiza el segundo, no el
  primero.

## 3. Las descripciones son abundantes `[VALIDADO-BD]`

| | total | con descripción | |
|---|---:|---:|---:|
| tablas | 2.411 | 1.883 | **78%** |
| columnas | 33.486 | 24.556 | **73%** |

Salen de los `COMMENTS` de Oracle, que el extractor parte por el separador `//`
en `description_es` / `description_en`. Es **prosa de negocio escrita por
humanos**, no DDL.

Y es más que un complemento: para las áreas sin documentación funcional (§10),
ese comentario es **la única documentación que existe**.

> No confundir ese separador con la convención `EN || ES` de los comentarios de
> **nuestro** código. Son cosas distintas; no unificarlas.

## 4. Vigencia: dos mecanismos, y ninguno es global

VisualTIME marca la vigencia de dos formas distintas `[TÁCITO]`:

- **Estado:** `SSTATREGT`.
- **Período:** `DEFFECDATE <= as_of AND (DNULLDATE > as_of OR DNULLDATE IS NULL)`.

### 4.1 Distribución medida `[VALIDADO-BD]`

De las 2.411 tablas, **1.492 tienen al menos una** de las tres columnas:

| mecanismo | tablas |
|---|---:|
| solo `SSTATREGT` | **879** |
| solo período completo (`DEFFECDATE` + `DNULLDATE`) | **440** |
| solo `DEFFECDATE`, sin `DNULLDATE` | 99 |
| **los dos mecanismos** | 38 |
| solo `DNULLDATE`, sin `DEFFECDATE` | 24 |
| `SSTATREGT` + una sola mitad del período | 12 |

Tres cosas que salen de ahí:

- **Las 722 `TABLE<n>` usan `SSTATREGT` y nada más, sin una sola excepción.**
- **Las 51 `TAR_*` (tarifas) son todas de período** — 42 con período puro y 8 con
  los tres. Coherente con lo que son: una tarifa vale para un rango de fechas. Y
  por eso la respuesta a *"¿cuánto vale esta tarifa?"* es **una serie con
  vigencias**, no un valor.
- **Las 123 con media pareja son una trampa**: `POLICY`, `CERTIFICAT`, `CHEQUES`,
  `NOTES` (solo `DNULLDATE`), `BANK_MOV`, `CHEQUE_MOV`, `ENTRIES` (solo
  `DEFFECDATE`). Son tablas transaccionales donde esas columnas significan otra
  cosa —fecha de anulación, fecha de efecto del movimiento— y el predicado ni
  siquiera cierra. **La presencia de la columna no implica el mecanismo.**

### 4.2 `SSTATREGT`: el catálogo es `TABLE26`, y solo el `1` cuenta

`[VALIDADO-BD]` Varias columnas `SSTATREGT` declaran en su descripción *"Estado
del registro. Valores posibles según **tabla 26**"*, y `TABLE26` tiene tres filas:

| valor | descripción declarada |
|---:|---|
| `1` | Activo |
| `2` | En proceso de instalación |
| `3` | Acceso restringido |

`[TÁCITO]` **El sistema solo contempla el valor `1`.** Los registros en `2` y `3`
existen en la base pero el sistema no los considera. Aportado por el usuario,
2026-09-09.

`[TÁCITO]` El valor **`4` es un error de datos** y se trata como `3`. Son 18
filas en `WINDOWS`; el valor no existe en `TABLE26`. Si una corrida futura trae
más, el error está creciendo y hay que avisarlo, no normalizarlo en silencio.

**Cómo se anota, y esto importa:** el campo derivado guarda **el estado
declarado** (`Activo`, `Acceso restringido`, `En proceso de instalación`) y, por
separado, el booleano de la regla operativa (`= 1`). Decirle a un usuario que una
transacción "fue dada de baja" cuando el catálogo dice *"acceso restringido"*
sería inventar: no son lo mismo, aunque para nuestro filtro tengan el mismo
efecto.

`[HIPÓTESIS]` **Que `WINDOWS` use `TABLE26` no está declarado.** La descripción
de `WINDOWS.SSTATREGT` es solo *"Estado del registro."*, sin referencia a tabla.
El catálogo **es por tabla**: otras columnas remiten a *"tabla 1541"*, *"535"*,
*"1520"*, y `CONFIGECONGROUP` declara directamente *"1 ACTIVO - 0 DESACTIVO"*.
Antes de aplicar `TABLE26` a otra tabla, verificar cuál es su catálogo.

### 4.3 La fecha de referencia es un parámetro, con default en la corrida

El predicado de período necesita una fecha, y **no puede ser `now()`**:

- Un snapshot de hace tres meses evaluado contra hoy afirma una vigencia que el
  dato no respalda.
- Y rompe los evals: una respuesta que depende del reloj de pared pasa hoy y
  falla la semana que viene sin que nadie haya tocado nada.

Default: el `created_at_utc` de la corrida vigente. Parametrizable, para poder
contestar *"¿qué estaba vigente en marzo de 2024?"* con los mismos datos.
(Detalle: `created_at_utc` es el reloj del extractor, no el `SYSDATE` de Oracle;
a granularidad de día es indistinto.)

### 4.4 El predicado, por tabla

| caso | regla |
|---|---|
| solo estado | `SSTATREGT = '1'` (con `4` → `3`) |
| solo período | `DEFFECDATE <= as_of AND (DNULLDATE > as_of OR DNULLDATE IS NULL)` |
| los dos (38 tablas) | los dos, **midiendo y reportando** la discrepancia |
| media pareja (123) | **sin mecanismo de vigencia declarado** — no se filtra, y se dice |
| ninguna columna | ídem |

Ese último estado explícito es lo que evita el defecto silencioso: una tabla sin
mecanismo no se filtra "por las dudas" ni a medias — se marca, y quien lee la
respuesta sabe que ahí no hay vigencia declarada.

Para las 38 con ambos mecanismos, la precedencia **no se supone: se mide**.
Contar las filas donde los dos criterios discrepan y decidir con ese número, como
se resolvió heurística-vs-`NWINDOWTY` (192 contra 205, difieren 19). Si discrepan
en cero filas, la pregunta se disuelve. Entre esas 38 están `LIFE_COVER`,
`GEN_COVER`, `COMMPLAN`, `TAB_COVROL`, `TAR_EARTHQ`, `UWHOMECRITERIAS` y
`UWICCRITERIAS` — configuración de producto, de lo más consultado.

## 5. Vincular un documento con su base: cinco vías medidas `[VALIDADO-BD]`

| vía | resultado | veredicto |
|---|---|---|
| `chunk.field` ↔ nombre físico de columna | 155 / 7.168 (**2,2%**) | **descartada** |
| `chunk.field` ↔ `descriptionEs` de la columna | 269 / 7.168 (**3,8%**) | **descartada** |
| `chunk.field` ↔ `FIELDSHEET.SFIELDDESC` | 482 / 7.167 (**6,7%**) | **descartada** |
| nombre de tabla mencionado en el texto del chunk | 563 tablas de 2.411 (**23%**) | viva, con caveat |
| `document_id` contenido en el nombre de una rutina | **578 documentos** / 1.622 pares | viva |
| código de transacción dentro de `description_es` | 56 pares, 37 con documento, **28 transacciones** | viva, angosta |

### 5.1 A nivel campo no hay puente, y está cerrado

Tres caminos independientes dieron el mismo veredicto. Se probaron **las dos
direcciones posibles** contra la columna física —su nombre y su descripción— y
después contra las 3.116 descripciones de campo de `FIELDSHEET`. Ninguna pasa del
7%.

La explicación: el documento funcional usa la **etiqueta de pantalla** ("Fecha de
vigencia") y la base tiene el **nombre físico** (`DFECVIG`); el nombre físico de
la columna **no aparece en la documentación en ninguna de sus formas**. No lo
arregla `pg_trgm` ni ninguna normalización: ese dato no está escrito.

**Implicancia:** `chunk.field` no sirve como clave de cruce con el diccionario. El
cruce funciona a nivel **tabla** y **transacción**. Los 482 pares de `FIELDSHEET`
sí valen como anotación declarada; no como mecanismo.

### 5.2 A nivel tabla sí, con un orden de magnitud de diferencia

563 de las 2.411 tablas aparecen nombradas literalmente en el texto del corpus.
Es coherente con que la spec de `retrieval` ya use `premium_mo` como escenario de
consulta real.

**Caveat pendiente:** la medición usó un token de 4+ caracteres, así que una tabla
llamada `TRACE` o `LEVELS` puede figurar por ser una palabra corriente. Los
nombres con `_` o con dígitos (`PREMIUM_MO`, `T_DOCTYP`, `TABLE88`) son
inequívocos; los alfabéticos puros hay que desambiguar. **Hueco de medición**, y
falta también la cobertura por documento.

### 5.3 Documento ↔ rutina: el corte está en el largo del código

| largo | pares | documentos | veredicto |
|---:|---:|---:|---|
| 4 | 7 | 2 | **falsos positivos** — `LOGO → INSCOPYCATALOGO`, `MENU → REAWINDOWSMENUPKG` |
| 5 | 472 | 130 | válidos — `CO003 → CALAMOUNTSCO003`, `SI008 → CALISRSI008` |
| 6 | 795 | 237 | válidos — `CAL013 → CAL013_FMT_VALIDATE` |
| ≥ 7 | 355 | 211 | **identidad**, no inferencia — `AU_C_RC → AU_C_RC`, `INSCALIVA → INSCALIVA` |

Descartando los de largo 4 quedan **578 documentos y 1.622 pares**. Encadenando
con `business_dependencies` da **documento → rutina → tablas**.

`[HIPÓTESIS]` Los de largo ≥ 7, donde el `document_id` **es** el nombre del objeto
Oracle, son los que `taxonomy.py` clasifica como `interface`; pendiente de
contrastar contra `transaction_type`.

### 5.4 Qué es un hecho y qué es un indicio

Las vías de identidad (§5.3, largo ≥ 7), `NG_IDENTI` (§7.1) y `MASTERSHEET`
(§9) producen **hechos declarados**. Las de coincidencia de nombre o de substring
producen **indicios con evidencia textual**. Un vínculo derivado de un substring
no puede presentarse como *"`CA014` usa la tabla `PREMIUM_MO`"*: va con su origen
y su fuerza, igual que las aristas del mapa de procesos llevan `edge_type` y
`origin`.

## 6. VisualTIME declara su propia estructura funcional en tablas `[VALIDADO-BD]`

La aplicación es **manejada por metadata**. Además de `WINDOWS`:

| tabla | filas | qué declara |
|---|---:|---|
| `WINDOWS` | 3.389 | ventanas, transacciones y menús del sistema |
| `SEQUEN_POL` | 19.525 | secuencias de ventanas para tratamiento de póliza |
| `LEVELS` | 15.766 | nivel de autorización por módulo/transacción y esquema |
| `TAB_WINPOL` | 14.193 | ventanas del tratamiento de pólizas (base del diseñador) |
| `WIN_ACTIONS` | 7.043 | acciones permitidas por transacción |
| `WIN_MESSAG` | ~2.365 | mensajes de error por ventana, con la acción correctiva |
| `MENU_SSCHE_CODE` | ~1.035 | menú por perfil |
| `TAB_WINCLA` / `TAB_WINPRO` / `TAB_WINCLI` | 374 / 203 / 93 | ídem siniestros, productos, clientes |
| `SEQFOLDER` | 301 | secuencia de carpetas de la consulta general (`GE099`) |
| `SCHE_TRANSAC` | 141 | transacciones permitidas por esquema de seguridad |
| `TABLE<n>` | 722 tablas / 14.661 filas | tablas genéricas de **contenido fijo** |

**Trampa de nombres.** `POLICY_WIN` (10.646.042 filas), `CLIENT_WIN` (9.962.135)
y `CLAIM_WIN` (461.459) **no son metadata**: son datos de negocio —qué ventanas
se ejecutaron sobre cada póliza, cliente o siniestro—. El parecido con
`TAB_WINPOL` invita al error; confundirlas mete diez millones de filas de datos
del cliente en lo que debería ser un mapa de navegación.

### 6.1 Las `TABLE<n>` son las `MAnnnn` del corpus `[VALIDADO-BD]`

`TABLE88` tiene 11 filas, y `visualtime-window-types.md` documenta que los tipos
de ventana salen de `MA0088`, *"tabla interna número 88, de valores fijos"*, y
lista exactamente 11. La correspondencia `MAnnnn` ↔ `TABLE<n>` queda validada, y
la columna que la declara es `WINDOWS.NG_IDENTI` (§7.1). De los 600 valores
distintos de `NG_IDENTI`, **397 (66%) tienen un documento `MAnnnn`** en el corpus.

## 7. `WINDOWS` declara mucho más de lo que se venía usando `[VALIDADO-BD]`

El `windows_tree.csv` que consume `app/generation/rag/navigation.py` tiene cinco
columnas (código, padre, descripción, tipo de ventana, descripción corta). La
tabla tiene 3.389 filas y, además:

| columna | poblada | qué es |
|---|---:|---|
| `SPSEUDO` | 3.385 | pseudónimo de la transacción — alias |
| `SCODISP` | 3.383 | código **físico** de la ventana (el lógico es `SCODISPL`) |
| `NMODULES` | 3.259 | código del módulo del sistema |
| `NG_IDENTI` | 1.937 | **la tabla genérica que mantiene la transacción** |
| `SSTATREGT` | 3.389 | estado del registro (§4.2) |
| `NAMELEVEL` / `NINQLEVEL` | — | niveles mínimos de actualización y consulta |
| `SHELPPATH`, `SDIRECTGO`, `SAUTOREP`, `SQUOTE`, `NTYPE_REPORT` | — | ayuda, acceso directo, reporte automático, cotizador, tipo de reporte |

Validación cruzada: la **descripción de la columna** `NWINDOWTY` enumera los 11
valores dentro del propio comentario, coincidiendo con lo que
`visualtime-window-types.md` había derivado de `MA0088`.

### 7.1 `NG_IDENTI` vale solo para el tipo de ventana 10 `[VALIDADO-BD]`

| tipo de ventana | ventanas | con `NG_IDENTI` ≠ 0 |
|---|---:|---:|
| **10 · Tabla general** | 605 | **603** |
| 3 · Masiva sin encabezado | 383 | 22 |
| 6 · Masivo con encabezado | 370 | 3 |
| 5 · Puntual sin encabezado | 522 | 2 |
| todos los demás | — | **0** |

Y la validación semántica confirma el corte: de los **529 pares** de tipo 10 que
resuelven a una `TABLE<n>` existente, **440 (83%) coinciden** entre el título de
la transacción y la descripción de la tabla. De los 11 pares de otros tipos,
**coinciden 0**.

Ejemplos del tipo 10: `MA0001` "Giro del negocio" → `TABLE1` "Giro del negocio";
`MA0004` "Conceptos de facturación generales" → `TABLE4` "Tabla de conceptos de
facturación generales"; `MA0007` "Bancos" → `TABLE7` "Bancos".

Contraejemplo de otro tipo: `COL504` "Libro de recaudación" con `NG_IDENTI = 2`
apuntando a `TABLE2` "Exclusión de cobertura por asegurado" — un reporte, no una
tabla general: **ahí el campo no significa nada.**

**Implicancia:** la arista *"esta transacción mantiene esta tabla"* se carga solo
para las ventanas de tipo 10, y es un **cuarto tipo de arista**, distinto de
`menu_parent`, `requires` y `references`.

## 8. `TAB_WINPOL` es secuencia declarada, pero **contextual** `[VALIDADO-BD]`

Columnas: `SBUSSITYP` (tipo de negocio), `SPOLITYPE` (tipo de póliza), `SCOMPON`
(componente), `NTRATYPEP` (tipo de transacción sobre la póliza), `NTYPE_AMEND`
(tipo de endoso), `SCODISPL`, `NSEQUENCE` (orden), `SREQUIRE` (ventana
requerida), `SDEFAULTI`, `SAUTOMATIC`.

**El orden y la obligatoriedad dependen de la combinación de producto**, no son
universales entre transacciones. Eso **no es** el `requires` del mapa de procesos,
que afirma precedencia sin condición. Cargarlas como el mismo tipo de arista
convertiría en universal algo que vale para una combinación. Si entra, entra como
un tipo propio con sus claves de contexto.

Dimensión: hoy la precedencia se infiere del texto y, de 228 secciones
`Requisitos`, solo **25** declaran algo. `TAB_WINPOL` tiene 14.193 filas.

## 9. Carga masiva e interfaces: un subsistema entero parametrizado `[VALIDADO-BD]`

La "carga masiva" de VisualTIME son procesos batch **parametrizados en tablas**:

```
producto (NBRANCH/NPRODUCT) → WORKSHEET (~41 plantillas)
                                  → COLSHEET (~1.525 columnas activas)
                                      → GROUP_COLUMNS (~543 campos → STABLE.SCOLUMNNAME)
interfaz (NSHEET) → MASTERSHEET (865 procesos → rutina PL/SQL en SPROCESS)
                        → FIELDSHEET (8.017 campos con SFIELDDESC → STABLE.SCOLUMNNAME)
```

Tres cosas que esto declara y que ninguna otra fuente tiene:

- **`MASTERSHEET.SPROCESS`** nombra el procedure que implementa cada interfaz
  (`INSPOSTGIL55385`), más `SROUTINE`, `SNAME_ROUTINE`, `SOUT_ROUTINE`, `SQUERY`,
  `NINTERTYPE` (entrada/salida), `SMASSIVE` y `SINDSCHEDULED` (corre programado).
- **`GROUP_COLUMNS` y `FIELDSHEET`** mapean campo → tabla y columna física. Es el
  puente campo↔columna **declarado**, aunque su cobertura contra el corpus sea
  del 6,7% (§5.1).
- **El modelo de propiedades de un objeto de riesgo** vive en la parametrización,
  no en el DDL: `TABLE6785` (tipos de riesgo) → `CAT_PROPERTY` (`NRISKTYPE` +
  `NDEFTYPE`, con `NDATATYPE`) → `CAT_PROPERTY_VALUE` (valores de lista) →
  `RISK_ATTRIBUTES` (`SREQUIRED`/`SENABLE` por `NCOVERGEN`). `RISKOBJECTDET`
  tiene cuatro columnas genéricas de valor y nada más, así que *"qué
  características tiene un objeto y cuáles son obligatorias"* **solo** se puede
  responder desde estas tablas.

De las 865 interfaces configuradas, con guarda de largo ≥ 4 apenas **~167
empalman con un documento** del corpus: es el subsistema con el hueco documental
más grande (§10).

`[HIPÓTESIS]` `NSHEET` empalma con los `document_id` del corpus para las
interfaces documentadas. Los `NSHEET` de 1 a 3 dígitos producen falsos positivos
masivos (9 interfaces de un dígito matchean 1.492 documentos): cualquier medición
sobre este puente necesita guarda de largo.

**Precaución de tamaño y de privacidad:** `SQUERY` y `SXSL` probablemente
contengan el SQL y el XSLT completos —lógica guardada como configuración—, y
`SPATH`/`SFOLDER` pueden llevar rutas de servidores del cliente. Medir su tamaño
antes de embeberlos.

## 10. Dos autoridades, y el diff es un entregable

`[TÁCITO]` **Hay transacciones que por errores de análisis nunca se documentaron.
La base refleja la versión actualizada del sistema.** Aportado por el usuario,
2026-09-09.

De ahí el principio que ordena todo el consumo:

- El **corpus** manda sobre la **intención funcional**: para qué sirve una
  transacción, qué regla aplica, qué valida.
- La **base** manda sobre **qué existe hoy**.

Cuando difieren no hay un error a resolver, hay un **hallazgo a reportar**. Y por
eso **nada se filtra por "aparece en el corpus"**: recortar por cobertura
documental borra justamente las áreas donde la documentación falla, que son las
que más falta hacen. El recorte, si hace falta, es por volumen o por tipo de
arista.

### 10.1 La medición del diff `[VALIDADO-BD]`

| estado de la ventana | ventanas | con documento | sin documento |
|---|---:|---:|---:|
| `1` Activo | 1.765 | 954 | **811** |
| `3` Acceso restringido | 1.588 | 570 | 1.018 |
| `2` En proceso de instalación | 18 | 4 | 14 |
| `4` (error de datos) | 18 | 0 | 18 |

**Documentación faltante.** De las 811 ventanas activas sin documento, 156 son
del tipo 8 (Menú) —carpetas, que no necesitan especificación funcional—. El hueco
real es de **~655 transacciones ejecutables activas sin documentar**, concentrado
en los tipos 2 (160) y 1 (157), seguidos por el tipo 10 (114).

**Documentación sobre lo no contemplado.** 574 documentos del corpus (570 en
estado `3` + 4 en estado `2`) describen transacciones que **el sistema no
contempla** (§4.2). Hoy el motor las recupera y las responde sin ninguna marca.

**La dirección inversa.** 648 de los 2.176 documentos no corresponden a ningún
`SCODISPL`:

- **282** son documentos de estructura (`ACCOUNTING_INDEX`, `ACCOUNTING_INTRO`,
  `ACCOUNTING_MARCOTEORICO`, `AG004_K`…) — esperable, no son transacciones.
- **364** son códigos que parecen transacciones reales (`AGC816`, `AGC842`,
  `BC003`, `BC668`).

`[HIPÓTESIS]` Esos 364 no son necesariamente obsoletos: la relación archivo ↔
transacción no es 1:1 (`ca001.md` → `CA001k`), y ahora hay dos columnas para
resolver alias, `SCODISP` y `SPSEUDO`. Reintentar el cruce contra ellas antes de
concluir nada.

### 10.2 Qué contesta el motor sobre algo no documentado

Ante una transacción o tabla sin documento, la respuesta correcta **no** es "no
existe" (falso) ni una narración armada desde el DDL (peor). Es: *existe, la base
la declara así, con estas columnas y estas descripciones, y no hay especificación
funcional que la describa* — con su `run_id` como respaldo.

Es la misma prevención que `cag.py` ya aplica al revés: *"un modelo que reciba el
mapa sin sus límites va a contestar que una transacción no existe cuando lo que
pasa es que no está en el menú"*.

**Límite honesto:** el diff se puede hacer a nivel transacción y a nivel tabla. A
nivel **columna no**, porque para cruzar campos documentados con columnas físicas
haría falta el puente que §5.1 descarta. Lo computable es *"esta tabla tiene N
columnas descriptas en la base y ninguna transacción documentada que la
mantenga"*.

## 11. Qué es catálogo: subsistemas, no prefijos

`[TÁCITO]` El diseñador de productos y la seguridad son los subsistemas que
definen **qué tipos de póliza se pueden emitir**, así que van completos. Aportado
por el usuario, 2026-09-09.

Los criterios, y su alcance real:

| criterio | qué captura | alcance |
|---|---|---|
| familias de nombre `TABLE<n>` / `TAB_*` / `TAR_*` | catálogos y tarifas | 886 tablas / 107.725 filas |
| columna `SSCHE_CODE` | **seguridad completa**: `SECUR_SCHE`, `LEVELS`, `SCHE_TRANSAC`, `SCHE_PCON`, `SCHE_PCON_LIMITS`, `SCHEMA_CUR`, `SCHE_SURR_*`, `MENU_SSCHE_CODE`, `LIMITS`, `OFF_ACC` | 16 tablas / ~18.039 filas |
| columnas `SBUSSITYP`/`SPOLITYPE`/`SCOMPON` | diseñador, **parcial** | 22 tablas |
| lista nombrada | metadata de ventanas, carga masiva, configuración global (`FORMATVALUES`, `NUMERATOR`) | ~35 tablas |
| **`WINDOWS.NG_IDENTI`** | **el criterio completo y declarado** | 529 pares de tipo 10 |

Dos cosas sobre esto:

- **El criterio por columna clave sobre- y sub-captura.** Sobre: `POLICY`
  (1.042.480 filas) y `TIN_UNDERWBOOK` (17.359.833) entran por llevar `SPOLITYPE`
  desnormalizado, y hay que excluirlas explícitamente. Sub: `PRODMASTER`,
  `GEN_COVER`, `COND_COVER`, `SECTION_PROD` y el núcleo del diseñador **no
  entran**, porque están indexadas por código de producto y ese nombre de columna
  todavía no se identificó. **Hueco pendiente.**
- **`NG_IDENTI` es el único criterio completo**, porque en una aplicación manejada
  por metadata una tabla de configuración tiene, por definición, una transacción
  de mantenimiento que la mantiene. `FORMATVALUES` y `NUMERATOR` lo demuestran:
  ningún criterio estructural los agarra.

El contraste con las transacciones `maintenance` del corpus sirve para **medir
cobertura**, nunca como filtro.

**Y lo excluido se lista con su motivo**, no se omite: `POLICY`,
`TIN_UNDERWBOOK`, `POLICY_WIN`/`CLIENT_WIN`/`CLAIM_WIN` (datos, no metadata),
`USERS`/`USERSWEB`/`ADVANCE_USERS` (datos personales: lo que responde *"quién
puede emitir qué"* son los esquemas, no las personas), y las de trabajo
(`TMP_*`, `T_*`, `%_TMP`, `%_BKP`, `%_1705`).

**Volumen total del catálogo: ~190.000 filas**, contra 1.418 millones de filas
transaccionales — el **0,013%** de la base. Ese número es el argumento medido de
por qué la extracción va **completa y sin filtros de vigencia**: la única razón
para filtrar en la extracción era el volumen, y el volumen es ruido.

## 12. Trampas de lectura `[VALIDADO-BD]`

- **El padding de `CHAR`.** `SCODISPL` viene rellenado (`"CA001k    "`) y las
  consultas del propio sistema fuente lo envuelven en `TRIM()`. Hay que
  normalizar **al cargar**, no al leer: al leer no usa el índice y alguien se lo
  va a olvidar.
- **Espacios de no separación.** 128 descripciones de `WINDOWS` tienen NBSP
  (U+00A0) en lugar de espacios: `"Preparación⍽Ctas.⍽Ctes."`. Una búsqueda con
  espacio normal no las encuentra.
- **`columns` es `jsonb` nullable.** `NULL` y `[]` no significan lo mismo: "no se
  extrajeron columnas" contra "la tabla no tiene". Ante `NULL` no hay evidencia.
- **`num_rows` es una estimación de Oracle**, la del `last_analyzed`, no un
  conteo. Sirve para dimensionar. Los conteos reales salen de `business_data`
  (`WINDOWS`: estimadas 3.341, reales 3.389).
- **`tenant`/`env` no es `tenant_id`/`doc_version`.** `env` es el ambiente de la
  base fuente; `doc_version` es la versión de la documentación. Cuál se cruza con
  cuál debe ser explícito, nunca inferido. `tenant` sí es el mismo concepto, con
  distinto largo (`VarChar(100)` contra `String(64)`).
- **`source_type` es homónimo y no significa lo mismo**: en `chunks` vale
  `functional_spec`; en `business_dependencies`, `PROCEDURE` / `VIEW` / …
- **El catálogo de estados es por tabla** (§4.2). No hay un `SSTATREGT` global.

## 13. Qué falta

**Cerrado por `add-window-status-metadata` (2026-09-09):**

- **`SSTATREGT` en el árbol que consume el servicio.** El CSV de cinco columnas no
  lo traía; el loader desde `visualtime.business_data` sí, con `BUSINESS_DB_RUN_ID`
  explícito. El chunk y el hit llevan el **estado declarado** (`Activo`, `Acceso
  restringido`, …) y el prompt advierte cuando no es activo.
- **Backfill de metadata** sobre los 56.537 chunks ya cargados, sin re-embedding.

**Sigue abierto:**

1. **La columna clave del producto** (`PRODUCT` / `PRODMASTER`), que habilita el
   núcleo del diseñador: `GEN_COVER`, `COND_COVER`, `SECTION_PROD`, `MODUL_CO_P`.
2. **Reconciliar la allowlist**: se cargaron 753 tablas de ~896 candidatas. Las
   ~143 que faltan son, presumiblemente, las que no tienen PK declarada —
   `primaryKeyColumns` es obligatorio en la config del extractor. Hay que listarlas
   y resolverlas con su índice único, no dejarlas caer.
3. **La precedencia entre los dos mecanismos de vigencia** en las 38 tablas que
   tienen los dos (§4.4), por conteo de discrepancias.
4. **Desambiguar las 563 tablas mencionadas** entre inequívocas y ambiguas, y
   medir la cobertura por documento (§5.2).
5. **Los 364 documentos sin ventana**, reintentados contra `SCODISP` y `SPSEUDO`.
6. **Contrastar los documentos de código largo** (§5.3) contra `transaction_type`.
7. **El significado de `SSTATREGT` en tablas que no remiten a `TABLE26`**.

## 14. Relación con las notas previas

- **Valida** `visualtime-window-types.md`: los 11 tipos aparecen enumerados en el
  comentario de `WINDOWS.NWINDOWTY`, y `TABLE88` tiene 11 filas.
- **Valida** §1 y §3 de `visualtime-navigation-taxonomy.md`: el árbol vive en
  `WINDOWS`, y el sistema declara nodo-vs-hoja además de derivarlo.
- **Agrega una dimensión que ninguna de las dos tenía:** el árbol que el servicio
  consume incluye 1.624 ventanas que el sistema no contempla, sin distinguirlas.
- **Contrasta** con §7 de la nota de taxonomía, que planteaba como `[HIPÓTESIS]`
  qué "fuente técnica en vivo" consultar por tipo de transacción. Hoy se puede
  responder con datos: para Funcional/ABM y Consulta, el cruce por nombre de tabla
  (§5.2) más las descripciones (§3); para Interfaz/Reporte, el vínculo con la
  rutina (§5.3) y `MASTERSHEET` (§9), **mucho más viable de lo que la nota
  esperaba** —la daba como "si se logra identificar"—. Lo que la hipótesis daba
  por descontado y resultó falso es el cruce a nivel campo (§5.1).

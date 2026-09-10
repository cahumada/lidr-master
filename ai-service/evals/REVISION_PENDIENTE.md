# Hoja de revisión — golden set de recuperación

> Derivado de `golden_retrieval.json` el 2026-09-10, corriendo `GET /search`
> con la configuración por default contra el corpus vigente. Es una **foto**:
> los ranks cambian si cambia el retriever o el corpus. Se borra cuando las 30
> queden revisadas.

**30 preguntas sin revisar** de 65. Por cada una:

1. ¿La haría un usuario real? (`question_is_realistic`)
2. ¿La anotación es correcta? (`annotation_is_correct`)
3. Si falta algún documento relevante, agregalo a `relevant_document_ids`.

La columna **rank** es la posición en la que el retriever devolvió el documento
anotado, con la config por default. `—` significa que no vino en el top 10:
eso NO invalida la anotación (puede ser un fallo de recuperación, que es
justamente lo que la métrica mide), pero si ninguno de los anotados aparece
vale mirar si la anotación apunta al documento equivocado.

## 1. `A-COL502` — collections / declared_precedence

> Que procesos hay que ejecutar antes de Imputación automática de PAC y Transbank (COL502)?

**Anotados** (4/4 en el top 10):

- `COL502` — rank **1**
- `CO501` — rank **3**
- `COL500` — rank **5**
- `COL704` — rank **6**

**Lo que trajo el retriever:**

1. `COL502` · Función general  ← anotado
2. `COL520` · Requisitos
3. `CO501` · Función general  ← anotado
4. `COL511` · Frecuencia de ejecución
5. `COL500` · Proceso batch  ← anotado
6. `COL704` · Función general  ← anotado
7. `COL585` · Requisitos
8. `COL636` · Requisitos
9. `COL742` · Proceso batch
10. `CPL999_k` · Requisitos

*Procedencia:* [Cobranzas] COL502 declara en su seccion Requisitos que requiere la ejecucion previa de CO501, COL500, COL704. Relevantes = el proceso mas su cadena declarada. Distractores = documentos de la familia COL que NO estan en la cadena.

---

## 2. `A-COL520` — collections / declared_precedence

> Que procesos hay que ejecutar antes de Notificación de cobranza PAC y Transbank (COL520)?

**Anotados** (2/4 en el top 10):

- `COL520` — rank **7**
- `CO501` — rank **—**
- `COL500` — rank **3**
- `COL704` — rank **—**

**Lo que trajo el retriever:**

1. `COL520_k` · Parámetros
2. `COL502` · Frecuencia de ejecución
3. `COL500` · Proceso batch  ← anotado
4. `COL511` · Frecuencia de ejecución
5. `COL585` · Requisitos
6. `COL636` · Requisitos
7. `COL520` · Proceso batch  ← anotado
8. `COLLECTIONS_INDEX` · VisualTIME
9. `GIL54538` · Proceso

*Procedencia:* [Cobranzas] COL520 declara en su seccion Requisitos que requiere la ejecucion previa de CO501, COL500, COL704. Relevantes = el proceso mas su cadena declarada. Distractores = documentos de la familia COL que NO estan en la cadena.

---

## 3. `B-policies-Código` — policies / field_validations

> Que validaciones existen sobre el campo Código en Polizas?

**Anotados** (3/6 en el top 10):

- `CA022` — rank **7**
- `CA024` — rank **—**
- `CA025` — rank **—**
- `CA028` — rank **6**
- `CA659` — rank **8**
- `CA727` — rank **—**

**Lo que trajo el retriever:**

1. `VI021` · Validaciones
2. `CAC1016` · Validaciones
3. `CAC1016A` · Validaciones
4. `CAC1016B` · Validaciones
5. `GIL54528` · Validaciones
6. `CA028` · Validaciones  ← anotado
7. `CA022` · Validaciones  ← anotado
8. `CA659` · Validaciones  ← anotado
9. `CAC001` · Validaciones
10. `CAC019` · Validaciones

*Procedencia:* [Polizas] Relevantes = los 6 documentos de policies con un chunk de Validaciones cuyo metadata.field es exactamente 'Código'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'código'.

---

## 4. `B-policies-Error/adv` — policies / field_validations

> Que validaciones existen sobre el campo Error/adv en Polizas?

**Anotados** (2/6 en el top 10):

- `CA028` — rank **—**
- `CA031` — rank **—**
- `CA034` — rank **—**
- `CA035` — rank **3**
- `CA401` — rank **6**
- `CA642` — rank **—**

**Lo que trajo el retriever:**

1. `VI009` · Validaciones
2. `GIL008` · Validaciones
3. `CA035` · Validaciones  ← anotado
4. `GIL009` · Validaciones
5. `COL907` · Validaciones
6. `CA401` · Validaciones  ← anotado
7. `SI738` · Validaciones
8. `MSI015` · Validaciones
9. `VIC732` · Validaciones
10. `SI501` · Validaciones

*Procedencia:* [Polizas] Relevantes = los 6 documentos de policies con un chunk de Validaciones cuyo metadata.field es exactamente 'Error/adv'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'error/adv'.

---

## 5. `B-policies-Fecha` — policies / field_validations

> Que validaciones existen sobre el campo Fecha en Polizas?

**Anotados** (5/6 en el top 10):

- `CAC013` — rank **7**
- `CAC016` — rank **10**
- `CAC019` — rank **8**
- `CAL006` — rank **—**
- `CAL010` — rank **9**
- `CAL400` — rank **1**

**Lo que trajo el retriever:**

1. `CAL400` · Validaciones  ← anotado
2. `GE010` · Campos
3. `AM006` · Validaciones
4. `CO722` · Validaciones
5. `CAL013_K` · Validaciones
6. `CA001M` · Validaciones
7. `CAC013` · Validaciones  ← anotado
8. `CAC019` · Validaciones  ← anotado
9. `CAL010` · Validaciones  ← anotado
10. `CAC016` · Validaciones  ← anotado

*Procedencia:* [Polizas] Relevantes = los 6 documentos de policies con un chunk de Validaciones cuyo metadata.field es exactamente 'Fecha'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'fecha'.

---

## 6. `B-policies-Rut_Contrante` — policies / field_validations

> Que validaciones existen sobre el campo Rut Contrante en Polizas?

**Anotados** (4/6 en el top 10):

- `CAC1005` — rank **5**
- `CAC1005A` — rank **—**
- `CAC1005B` — rank **—**
- `CAC1006` — rank **2**
- `CAC1006A` — rank **4**
- `CAC1006B` — rank **3**

**Lo que trajo el retriever:**

1. `CAC960` · Validaciones
2. `CAC1006` · Validaciones  ← anotado
3. `CAC1006B` · Validaciones  ← anotado
4. `CAC1006A` · Validaciones  ← anotado
5. `CAC1005` · Campos  ← anotado
6. `CAC849` · Campos
7. `CAC950` · Campos
8. `CAC1021` · Campos
9. `CAC947` · Campos
10. `GIL101` · Campos

*Procedencia:* [Polizas] Relevantes = los 6 documentos de policies con un chunk de Validaciones cuyo metadata.field es exactamente 'Rut Contrante'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'rut'.

---

## 7. `C-CA036_k` — policies / by_code

> Que hace CA036_k?

**Anotados** (1/1 en el top 10):

- `CA036_k` — rank **1**

**Lo que trajo el retriever:**

1. `CA036_k` · Notas al programador  ← anotado
2. `CA036_A` · Información técnica
3. `CA039` · Notas para el programador
4. `MS010_K` · Introducción
5. `MCA505` · Información técnica
6. `MCA400` · Información técnica
7. `CA001k` · Efecto
8. `CA006` · Validaciones
9. `MCA400_k` · Función
10. `SGC001_k` · Campos

*Procedencia:* [Polizas] Relevante = CA036_k ('Facturación de colectivos', tipo key_request). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia CA.

---

## 8. `C-CA035` — policies / by_code

> Que hace CA035?

**Anotados** (1/1 en el top 10):

- `CA035` — rank **1**

**Lo que trajo el retriever:**

1. `CA035` · Información técnica  ← anotado
2. `POLICIES_INDEX` · VisualTIME
3. `NC012a` · Notas para el programador
4. `SCA500` · Si alguno de los componentes tiene definido solo dos criterios de información adicional, aparecerán solo el título del componente.
5. `CA027` · Notas al programador
6. `BC967` · Campos
7. `CA050` · Notas para el programador
8. `CA006` · Validaciones
9. `CA037` · Validaciones
10. `CA028` · Validaciones

*Procedencia:* [Polizas] Relevante = CA035 ('Datos para la suspensión de la póliza o certificado', tipo functional_abm). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia CA.

---

## 9. `C-CAC910` — policies / by_code

> Que hace CAC910?

**Anotados** (1/1 en el top 10):

- `CAC910` — rank **1**

**Lo que trajo el retriever:**

1. `CAC910` · Información técnica  ← anotado
2. `CAC900` · Notas para el programador
3. `CAC991` · Información técnica
4. `CAC916` · Notas para el programador
5. `CAC985` · Información técnica
6. `CAC992` · Campos
7. `CAC912` · Información técnica
8. `CAC989` · Acciones de menú
9. `CAC951` · Información técnica
10. `CAC970` · Información técnica

*Procedencia:* [Polizas] Relevante = CAC910 ('Consulta de Propuestas en Espera de Pago de Prima(`CAC910`)', tipo query). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia CAC.

---

## 10. `B-claims-Caso` — claims / field_validations

> Que validaciones existen sobre el campo Caso en Siniestros?

**Anotados** (2/8 en el top 10):

- `SI008_k` — rank **1**
- `SI011` — rank **—**
- `SI012` — rank **—**
- `SI017` — rank **6**
- `SI025` — rank **—**
- `SI776` — rank **—**
- `SI831` — rank **—**
- `SIC004` — rank **—**

**Lo que trajo el retriever:**

1. `SI008_k` · Validaciones  ← anotado
2. `CO823` · Validaciones
3. `SI004` · Validaciones
4. `OS001` · Validaciones
5. `SI010_k` · Campos
6. `SI017` · Validaciones  ← anotado
7. `SIC002` · Campos
8. `SI007` · Campos
9. `SIL1067` · Validaciones
10. `SIL005` · Validaciones

*Procedencia:* [Siniestros] Relevantes = los 8 documentos de claims con un chunk de Validaciones cuyo metadata.field es exactamente 'Caso'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'caso'.

---

## 11. `B-claims-Cliente` — claims / field_validations

> Que validaciones existen sobre el campo Cliente en Siniestros?

**Anotados** (3/7 en el top 10):

- `SI004` — rank **1**
- `SI022` — rank **—**
- `SI629` — rank **7**
- `SI737` — rank **—**
- `SI776` — rank **—**
- `SIC001` — rank **4**
- `SIC643` — rank **—**

**Lo que trajo el retriever:**

1. `SI004` · Validaciones  ← anotado
2. `GIL008` · Campos
3. `DP056` · Validaciones
4. `SIC001` · Validaciones  ← anotado
5. `VI009` · Validaciones
6. `OPC012` · Validaciones
7. `SI629` · Validaciones  ← anotado
8. `OPC014_k` · Validaciones
9. `OPC015_k` · Validaciones
10. `SI018` · Vali_ daciones

*Procedencia:* [Siniestros] Relevantes = los 7 documentos de claims con un chunk de Validaciones cuyo metadata.field es exactamente 'Cliente'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'cliente'.

---

## 12. `B-claims-Producto` — claims / field_validations

> Que validaciones existen sobre el campo Producto en Siniestros?

**Anotados** (3/7 en el top 10):

- `SI001_k` — rank **7**
- `SI737` — rank **—**
- `SI773` — rank **—**
- `SI777` — rank **2**
- `SIC002` — rank **—**
- `SIL005` — rank **—**
- `SIL00970` — rank **6**

**Lo que trajo el retriever:**

1. `GIL008` · Validaciones
2. `SI777` · Validaciones  ← anotado
3. `MSI010` · Validaciones
4. `GIL009` · Validaciones
5. `MAU587` · Validaciones
6. `SIL00970` · Validaciones  ← anotado
7. `SI001_k` · Validaciones  ← anotado
8. `VI009` · Validaciones
9. `CAC013` · Validaciones
10. `DPC997` · Validaciones

*Procedencia:* [Siniestros] Relevantes = los 7 documentos de claims con un chunk de Validaciones cuyo metadata.field es exactamente 'Producto'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'producto'.

---

## 13. `B-claims-Ramo` — claims / field_validations

> Que validaciones existen sobre el campo Ramo en Siniestros?

**Anotados** (3/7 en el top 10):

- `SI001_k` — rank **—**
- `SI501_k` — rank **1**
- `SI737` — rank **—**
- `SI773` — rank **—**
- `SI777` — rank **2**
- `SIC002` — rank **—**
- `SIL00970` — rank **6**

**Lo que trajo el retriever:**

1. `SI501_k` · Validaciones  ← anotado
2. `SI777` · Validaciones  ← anotado
3. `MSI014` · Validaciones
4. `MSI010` · Validaciones
5. `MSI015` · Validaciones
6. `SIL00970` · Validaciones  ← anotado
7. `CAC900` · Validaciones
8. `CAC013` · Validaciones
9. `VI009` · Validaciones
10. `AG553` · Validaciones

*Procedencia:* [Siniestros] Relevantes = los 7 documentos de claims con un chunk de Validaciones cuyo metadata.field es exactamente 'Ramo'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'ramo'.

---

## 14. `C-SI010_k` — claims / by_code

> Que hace SI010_k?

**Anotados** (1/1 en el top 10):

- `SI010_k` — rank **1**

**Lo que trajo el retriever:**

1. `SI010_k` · Campos  ← anotado
2. `SI010` · Información técnica
3. `INT9993` · Información técnica
4. `GIL210` · Información técnica
5. `SI501` · Información técnica
6. `INT54126` · Información técnica
7. `INT54130` · Información técnica
8. `GIL008` · Información técnica
9. `INT54544` · Información técnica
10. `INT9991` · Información técnica

*Procedencia:* [Siniestros] Relevante = SI010_k ('Solicitud de siniestro a procesar', tipo key_request). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia SI.

---

## 15. `C-SI025` — claims / by_code

> Que hace SI025?

**Anotados** (1/1 en el top 10):

- `SI025` — rank **1**

**Lo que trajo el retriever:**

1. `SI025` · Información técnica  ← anotado
2. `SI021` · Información técnica
3. `GIL109` · Información técnica
4. `GIL216` · Información técnica
5. `GIL100` · Información técnica
6. `GIL003` · Información técnica
7. `GIL200` · Información técnica
8. `GIL215` · Información técnica
9. `GIL226` · Información técnica
10. `GIL54535` · Información técnica

*Procedencia:* [Siniestros] Relevante = SI025 ('Reservas de atención médica', tipo functional_abm). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia SI.

---

## 16. `C-SIC005` — claims / by_code

> Que hace SIC005?

**Anotados** (1/1 en el top 10):

- `SIC005` — rank **1**

**Lo que trajo el retriever:**

1. `SIC005` · Función general  ← anotado
2. `SIC643` · Campos
3. `SIC500` · Campos
4. `SIC002` · Campos
5. `SIC004` · Campos
6. `SI501` · Información técnica
7. `CLAIMS-INDEX` · VisualTIME
8. `INT54561` · Características de la interfaz
9. `INT54130` · Información técnica
10. `INT54126` · Información técnica

*Procedencia:* [Siniestros] Relevante = SIC005 ('Consulta de operaciones de siniestros', tipo query). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia SIC.

---

## 17. `B-collections-Certificado` — collections / field_validations

> Que validaciones existen sobre el campo Certificado en Cobranzas?

**Anotados** (4/8 en el top 10):

- `CO001` — rank **5**
- `CO001_k` — rank **8**
- `CO510_k` — rank **9**
- `CO632_k` — rank **—**
- `CO633A` — rank **—**
- `CO722` — rank **—**
- `COC897` — rank **—**
- `COC902` — rank **1**

**Lo que trajo el retriever:**

1. `COC902` · Validaciones  ← anotado
2. `SIL005` · Validaciones
3. `CA035` · Validaciones
4. `VIC006` · Validaciones
5. `CO001` · Validaciones  ← anotado
6. `VI009` · Validaciones
7. `CAC011` · Validaciones
8. `CO001_k` · Validaciones  ← anotado
9. `CO510_k` · Validaciones  ← anotado
10. `VI7000` · Validaciones

*Procedencia:* [Cobranzas] Relevantes = los 8 documentos de collections con un chunk de Validaciones cuyo metadata.field es exactamente 'Certificado'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'certificado'.

---

## 18. `B-collections-Fecha_final` — collections / field_validations

> Que validaciones existen sobre el campo Fecha final en Cobranzas?

**Anotados** (5/8 en el top 10):

- `CO700_k` — rank **2**
- `CO701_k` — rank **—**
- `COL524` — rank **3**
- `COL686` — rank **1**
- `COL723` — rank **—**
- `COL829` — rank **6**
- `COL888` — rank **4**
- `COL907` — rank **—**

**Lo que trajo el retriever:**

1. `COL686` · Validaciones  ← anotado
2. `CO700_k` · Validaciones  ← anotado
3. `COL524` · Validaciones  ← anotado
4. `COL888` · Validaciones  ← anotado
5. `VIL904` · Validaciones
6. `COL829` · Validaciones  ← anotado
7. `AGC002` · Validaciones
8. `AGL014` · Validaciones
9. `SIL1065` · Validaciones
10. `CAC941` · Validaciones

*Procedencia:* [Cobranzas] Relevantes = los 8 documentos de collections con un chunk de Validaciones cuyo metadata.field es exactamente 'Fecha final'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'fecha'.

---

## 19. `B-collections-Compañía` — collections / field_validations

> Que validaciones existen sobre el campo Compañía en Cobranzas?

**Anotados** (2/7 en el top 10):

- `COC998` — rank **—**
- `COL1029` — rank **—**
- `COL1030` — rank **—**
- `COL938` — rank **1**
- `COL953` — rank **2**
- `COL981` — rank **—**
- `COL987` — rank **—**

**Lo que trajo el retriever:**

1. `COL938` · Validaciones  ← anotado
2. `COL953` · Validaciones  ← anotado
3. `CAC1016A` · Validaciones
4. `CAC1016B` · Validaciones
5. `CAC1016` · Validaciones
6. `AGC904` · Validaciones
7. `OPL922` · Validaciones
8. `OP715` · Validaciones
9. `DPC983` · Validaciones
10. `OPL1062` · Validaciones

*Procedencia:* [Cobranzas] Relevantes = los 7 documentos de collections con un chunk de Validaciones cuyo metadata.field es exactamente 'Compañía'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'compañía'.

---

## 20. `B-collections-Fecha_inicial` — collections / field_validations

> Que validaciones existen sobre el campo Fecha inicial en Cobranzas?

**Anotados** (3/7 en el top 10):

- `CO700_k` — rank **2**
- `CO701_k` — rank **—**
- `COL524` — rank **1**
- `COL723` — rank **8**
- `COL829` — rank **—**
- `COL888` — rank **—**
- `COL907` — rank **—**

**Lo que trajo el retriever:**

1. `COL524` · Validaciones  ← anotado
2. `CO700_k` · Validaciones  ← anotado
3. `MAG554` · Validaciones
4. `SIL001` · Validaciones
5. `VIL891` · Validaciones
6. `OPL020` · Validaciones
7. `CAC941` · Validaciones
8. `COL723` · Validaciones  ← anotado
9. `CO003` · Validaciones
10. `CO005` · Validaciones

*Procedencia:* [Cobranzas] Relevantes = los 7 documentos de collections con un chunk de Validaciones cuyo metadata.field es exactamente 'Fecha inicial'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'fecha'.

---

## 21. `C-CO513` — collections / by_code

> Que hace CO513?

**Anotados** (1/1 en el top 10):

- `CO513` — rank **1**

**Lo que trajo el retriever:**

1. `CO513` · Efecto  ← anotado
2. `MCO513` · Notas para el programador
3. `CO510` · Validaciones
4. `CO510_k` · Notas para el programador
5. `MCO505` · Validaciones
6. `MCO511` · Función
7. `MCO678` · Función
8. `MCO506` · Función
9. `MCO514` · Notas para el programador
10. `MCO508` · Campos

*Procedencia:* [Cobranzas] Relevante = CO513 ('Boletines de una relación', tipo functional_abm). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia CO.

---

## 22. `C-CO701_k` — collections / by_code

> Que hace CO701_k?

**Anotados** (1/1 en el top 10):

- `CO701_k` — rank **1**

**Lo que trajo el retriever:**

1. `CO701_k` · Función  ← anotado
2. `CO701` · Información técnica
3. `CO701A` · Función
4. `CO700_k` · Función
5. `CO700` · Información técnica
6. `COL700_B` · Función general
7. `CO700A` · Efecto
8. `CO510_k` · Notas para el programador
9. `CO510` · Información técnica
10. `CO001_k` · Campos

*Procedencia:* [Cobranzas] Relevante = CO701_k ('Datos generales para la impresión', tipo key_request). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia CO.

---

## 23. `C-COC1105` — collections / by_code

> Que hace COC1105?

**Anotados** (1/1 en el top 10):

- `COC1105` — rank **1**

**Lo que trajo el retriever:**

1. `COC1105` · Campos  ← anotado
2. `DPC997` · Notas para el programador
3. `COC897` · Campos
4. `MA5551` · Función
5. `CO685` · Información técnica
6. `COC006` · Información técnica
7. `COC005` · Información técnica
8. `COLLECTIONS_INDEX` · VisualTIME
9. `COC001` · Información técnica
10. `CO510` · Información técnica

*Procedencia:* [Cobranzas] Relevante = COC1105 ('Consulta detalle de convenio', tipo query). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia COC.

---

## 24. `B-designer-Producto` — designer / field_validations

> Que validaciones existen sobre el campo Producto en Disenador?

**Anotados** (3/8 en el top 10):

- `DP002` — rank **2**
- `DP003_k` — rank **5**
- `DP017` — rank **—**
- `DP063` — rank **—**
- `DP770` — rank **—**
- `DPC834` — rank **—**
- `DPC927` — rank **—**
- `DPC997` — rank **1**

**Lo que trajo el retriever:**

1. `DPC997` · Validaciones  ← anotado
2. `DP002` · Validaciones  ← anotado
3. `ST005` · Validaciones
4. `VIL733` · Validaciones
5. `DP003_k` · Validaciones  ← anotado
6. `AG553` · Validaciones
7. `SI737` · Validaciones
8. `AGC957` · Validaciones
9. `CAC008` · Validaciones
10. `CAC900` · Validaciones

*Procedencia:* [Disenador] Relevantes = los 8 documentos de designer con un chunk de Validaciones cuyo metadata.field es exactamente 'Producto'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'producto'.

---

## 25. `B-designer-Moneda` — designer / field_validations

> Que validaciones existen sobre el campo Moneda en Disenador?

**Anotados** (2/7 en el top 10):

- `DP018G` — rank **9**
- `DP029` — rank **10**
- `DP031` — rank **—**
- `DP036` — rank **—**
- `DP039` — rank **—**
- `DP043` — rank **—**
- `DP578A` — rank **—**

**Lo que trajo el retriever:**

1. `MVI706` · Validaciones
2. `AG005` · Validaciones
3. `OP092_k` · Validaciones
4. `CR304` · Validaciones
5. `BC014` · Validaciones
6. `DP003` · Validaciones
7. `CR301` · Validaciones
8. `CA403` · Validaciones
9. `DP018G` · Validaciones  ← anotado
10. `DP029` · Validaciones  ← anotado

*Procedencia:* [Disenador] Relevantes = los 7 documentos de designer con un chunk de Validaciones cuyo metadata.field es exactamente 'Moneda'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'moneda'.

---

## 26. `B-designer-Cobertura` — designer / field_validations

> Que validaciones existen sobre el campo Cobertura en Disenador?

**Anotados** (3/6 en el top 10):

- `DP017` — rank **—**
- `DP018G_K` — rank **4**
- `DP029_K` — rank **2**
- `DP064` — rank **—**
- `DP101` — rank **—**
- `DPC997` — rank **1**

**Lo que trajo el retriever:**

1. `DPC997` · Validaciones  ← anotado
2. `DP029_K` · Validaciones  ← anotado
3. `MAP005_k` · Validaciones
4. `DP018G_K` · Validaciones  ← anotado
5. `DP033` · Validaciones
6. `CR724` · Validaciones
7. `CR731` · Validaciones
8. `CR572` · Validaciones
9. `AM003` · Validaciones
10. `DPC926` · Validaciones

*Procedencia:* [Disenador] Relevantes = los 6 documentos de designer con un chunk de Validaciones cuyo metadata.field es exactamente 'Cobertura'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'cobertura'.

---

## 27. `B-designer-Código` — designer / field_validations

> Que validaciones existen sobre el campo Código en Disenador?

**Anotados** (1/6 en el top 10):

- `DP008` — rank **—**
- `DP033` — rank **—**
- `DP036` — rank **3**
- `DP100` — rank **—**
- `DP809` — rank **—**
- `DP810` — rank **—**

**Lo que trajo el retriever:**

1. `MCA632` · Validaciones
2. `ST003` · Validaciones
3. `DP036` · Validaciones  ← anotado
4. `AGC904` · Validaciones
5. `MGI1400` · Validaciones
6. `MSI015` · Validaciones
7. `BC005_k` · Validaciones
8. `VI021` · Validaciones
9. `MCO827` · Validaciones
10. `MOP702` · Validaciones

*Procedencia:* [Disenador] Relevantes = los 6 documentos de designer con un chunk de Validaciones cuyo metadata.field es exactamente 'Código'. Distractores = documentos que validan OTRO campo cuyo nombre contiene 'código'.

---

## 28. `C-DP042` — designer / by_code

> Que hace DP042?

**Anotados** (1/1 en el top 10):

- `DP042` — rank **1**

**Lo que trajo el retriever:**

1. `DP042` · Efecto  ← anotado
2. `DP004` · Notas para el programador
3. `DP003_A` · Información técnica
4. `DP036` · Función
5. `DP043C` · Función
6. `DP038` · Función
7. `DP034` · Función
8. `DP043` · Campos
9. `DP008` · Campos
10. `DP059` · Información técnica

*Procedencia:* [Disenador] Relevante = DP042 ('Clientes permitidos', tipo functional_abm). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia DP.

---

## 29. `C-DP034_K` — designer / by_code

> Que hace DP034_K?

**Anotados** (1/1 en el top 10):

- `DP034_K` — rank **1**

**Lo que trajo el retriever:**

1. `DP034_K` · Introducción  ← anotado
2. `DP034` · Función
3. `DP034_A` · Información técnica
4. `DP018_K` · Introducción
5. `DP039` · Información técnica
6. `DP029_A` · Información técnica
7. `DP018_A` · Información técnica
8. `DP003_A` · Información técnica
9. `DP036` · Función
10. `DP08B1` · Función

*Procedencia:* [Disenador] Relevante = DP034_K ('Datos de referencia de la cobertura', tipo key_request). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia DP.

---

## 30. `C-DPC982` — designer / by_code

> Que hace DPC982?

**Anotados** (1/1 en el top 10):

- `DPC982` — rank **1**

**Lo que trajo el retriever:**

1. `DPC982` · Información técnica  ← anotado
2. `DPC996` · Información técnica
3. `DPC997` · Información técnica
4. `DPC983` · Información técnica
5. `DPC925` · Información técnica
6. `DPC926` · Notas para el programador
7. `DPC927` · Campos
8. `DPC994` · Información técnica
9. `DPC995` · Notas para el programador
10. `DPC834` · Notas para el programador

*Procedencia:* [Disenador] Relevante = DPC982 ('Consulta de Planes según Ramo, Subramo, Producto (`DPC982`)', tipo query). Un solo relevante por construccion: la pregunta nombra un codigo. Distractores = documentos de la familia DPC.

---

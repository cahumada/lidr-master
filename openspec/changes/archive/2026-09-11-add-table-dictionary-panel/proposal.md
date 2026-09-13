## Why

El bloque de base nombra las tablas que toca una transacción y **no dice qué es
ninguna**:

```
- CESSION_NPR [rol no declarado] — 1/1 rutinas; vía INSCRL050.
- CESSION_PR [rol no declarado] — 1/1 rutinas; vía INSCRL050.
```

Para una pregunta sobre reaseguro no proporcional, esos dos nombres son
exactamente la respuesta —uno es no proporcional y el otro proporcional— y el
modelo no tiene cómo saberlo. `business_tables` lo declara en prosa de negocio:
*«Cesiones de primas no proporcionales de reaseguro»*, *«Cesiones de prima de
reaseguro»*.

**El renderer ya tiene la línea y nunca se emite.** `render.py` hace
`if table.description:` y `read_dependency_tables` construye el
`DependencyTable` sin ese campo, así que la condición jamás se cumple. No es una
feature nueva: es una que quedó a medio conectar.

Y hay un segundo hueco, del lado de quien opera: **las columnas no están en
ningún lado**. `business_tables` trae 33.486 columnas con 24.556 descripciones
(73%), 1.881 PK y 2.096 FK declaradas, y nada de eso se puede mirar. Medido, el
diccionario completo de 12 tablas son **15.969 tokens**, así que meterlo al
prompt en cada turno no es una opción: tu turno de ejemplo usaba 7.045 de
entrada y el techo del contexto es 16.384.

## What Changes

- **La descripción de la tabla viaja al prompt.** `read_dependency_tables` hace
  `LEFT JOIN` con `business_tables` por `(tenant, env, run_id, name)` — una
  consulta, no N+1. Medido sobre los 3 códigos con tablas de un turno real:
  las 36 tablas tienen descripción y cuestan **+373 tokens**.
- **El techo del bloque sube a 3.072.** Con las descripciones el bloque pasa de
  1.980 a 2.353 y el techo era 2.048: sin esto el recorte empezaría a comer
  tablas el mismo día que entra la feature. Se sigue cobrando adentro de
  `ANSWER_MAX_CONTEXT_TOKENS`.
- **Las columnas NO van al prompt.** Van a la consola, a demanda: un endpoint
  propio y un panel desplegable por tabla, con las columnas y su descripción, el
  tipo, si admite nulos, la PK, las FK con su tabla destino, y los índices.
  Cuesta cero tokens por turno y muestra las 132 columnas de `CERTIFICAT` cuando
  alguien las pide, no en cada pregunta.
- **La ficha la ve cualquier sesión, no solo `administrador`.** El bloque de base
  ya se le muestra a todos en el turno y la ficha es más de la misma autoridad.
  Lo que sí queda restringido es el prompt completo, que lleva la persona y los
  guardrails — eso no cambia.

Fuera de alcance, con su motivo:

- **El diccionario completo en el prompt.** Medido: 15.969 tokens para 12 tablas,
  y filtrar a «solo columnas con descripción» baja apenas a 15.617 porque el
  volumen está justamente en las documentadas. Entra si se suben los techos, pero
  **nadie midió si mejora la respuesta**: 16.000 tokens de definiciones de columna
  junto a 7.000 de evidencia funcional pueden ayudar o pueden enterrarla, y el
  bloque va al final del system, que es donde peor se lee. Es un change propio,
  con `eval_generation.py` decidiendo entre compacto, escalonado y completo.
- **Fijar una tabla para que persista entre turnos.** Los anchors de hoy son
  restricciones de ALCANCE sobre la búsqueda (`transaction_prefix`,
  `window_type_name`, `module_code`) y los consume `query_planner` como filtros.
  Inyectar contenido es la operación inversa, y meterla como un `AnchorKind`
  nuevo haría que el tipo signifique «restricción de alcance… o a veces no».
  Necesita concepto propio, y antes hace falta saber si el caso existe.

## Capabilities

### Modified Capabilities

- `business-db-context`: cada tabla emitida dice qué es, con la prosa de negocio
  que declara la corrida.
- `web-console`: el diccionario completo de una tabla se abre desde el panel de
  contexto de base, sin costo de prompt.

## Impact

- `ai-service/app/generation/rag/business_db/reader.py` — el join y una lectura
  nueva del diccionario completo.
- `ai-service/app/api/business_db.py` — `GET /business-db/tables/{name}`.
- `ai-service/app/config.py`, `ai-service/.env.example` — el techo a 3.072.
- `ai-service/tests/generation/rag/business_db/`, `ai-service/tests/api/` — tests.
- `business-backend/lib/ai-service/types.ts`, `business-backend/lib/ai-service/business-db.ts` — el contrato.
- `business-backend/app/api/business-db/tables/[name]/route.ts` — nuevo.
- `business-backend/app/(console)/answer/table-dictionary.tsx` — nuevo.
- `business-backend/app/(console)/answer/business-db-panel.tsx` — el link.
- `openspec/standards/app-routes.md` — las dos rutas nuevas.

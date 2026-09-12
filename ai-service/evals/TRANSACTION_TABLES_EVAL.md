# Tablas por transaccion - evaluacion

Corrida `20260909_214921` - tope `12` - 4 casos anotados.

| codigo | anotadas | en el tope | recall@N | posiciones | tablas totales |
|---|---:|---:|---:|---|---:|
| `CA014` | 1 | 1 | 100% | COVER#1 | 38 |
| `CA025` | 2 | 2 | 100% | ROLES#2, CLIENT#1 | 18 |
| `CA001` | 3 | - | - | sin aristas | 0 |
| `CA048` | 3 | 2 | 67% | POLICY#15, CERTIFICAT#1, POLICY_HIS#2 | 18 |

**recall@12 global: 56%** (5/9).
Peor posicion de una tabla anotada: 15.

## Roles emitidos dentro del tope

| rol | tablas |
|---|---:|
| `unknown` | 30 |
| `historical` | 4 |
| `reference` | 1 |
| `validation` | 1 |

## Veredicto

**Habilitar `BUSINESS_DB_DEPENDENCY_TABLES_ENABLED`: NO.**
Hacen falta 20 casos anotados y recall >= 90%; hay 4 casos y recall 56%.

No hay una columna de precision de `core` porque no hay rol `core`:
ninguna senal declarada lo aisla y el fan-in bajo que proponia el plan
corre al reves. Ver `app/generation/rag/business_db/roles.py`.

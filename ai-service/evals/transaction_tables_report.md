# Tablas por transaccion - reporte de construccion

Corrida del mirror: `20260909_214921` - corpus: `DW Funtionals 2026.1`

| | |
|---|---:|
| documentos del corpus | 2176 |
| documentos que resuelven 1+ rutina | 460 |
| pares codigo-rutina | 957 |
| documentos que llegan a 1+ tabla | 460 |
| aristas codigo-tabla | 4873 |
| tablas por documento (mediana) | 7 |
| rutinas cedidas por munch maximo | 61 |

## Aristas por rol

| rol | aristas |
|---|---:|
| `unknown` | 4046 |
| `reference` | 507 |
| `validation` | 189 |
| `historical` | 115 |
| `message` | 16 |

`unknown` no es un defecto del batch: es lo que ninguna regla declarada
clasificó. Ver `app/generation/rag/business_db/roles.py` para por qué no
hay un rol `core`.

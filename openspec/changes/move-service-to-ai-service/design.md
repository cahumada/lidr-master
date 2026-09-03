## Lo que la mudanza podría romper, y por qué no lo hace

La pregunta que importa no es "¿dónde va cada archivo?" sino "¿qué se rompe en
silencio?". Tres candidatos, verificados uno por uno.

### 1. Las rutas que el código calcula solo

Ningún archivo de este repo tiene una ruta absoluta ni una ruta relativa al
directorio de trabajo. Todos derivan su raíz del propio archivo:

| archivo | cómo deriva la raíz | a qué apunta después de mover |
|---|---|---|
| los 8 scripts del pipeline | `sys.path.insert(0, __file__.parent.parent)` | `ai-service/` ✓ |
| `alembic/env.py` | ídem | `ai-service/` ✓ |
| `alembic.ini` | `script_location = %(here)s/alembic` | `ai-service/alembic` ✓ |
| `tests/generation/rag/*` | `parents[3] / "data"` | `ai-service/data` ✓ |
| `tests/test_embed_corpus_script.py` | `parents[1] / "scripts"` | `ai-service/scripts` ✓ |
| `pyproject.toml` | `testpaths = ["tests"]`, relativo al propio archivo | `ai-service/tests` ✓ |

La condición que hace verdadera toda la columna derecha es una sola: **`data/`
viaja con el código**. Si `data/` se quedara en la raíz, los cinco tests que
leen documentos reales fallarían por archivo faltante — ruidosamente, no en
silencio, que es lo aceptable.

### 2. El volumen de Postgres

`docker-compose.yml` declara el volumen `pgdata`. Docker Compose lo prefija con
el nombre del proyecto, que por defecto **es el nombre del directorio donde
está el archivo**. Hoy: `lidr-master_pgdata`. Si el compose se mudara a
`ai-service/`, pasaría a ser `ai-service_pgdata`: un volumen nuevo y vacío, y
un `docker compose up -d` que arranca sin error contra una base sin las 57.101
filas cargadas.

El curso aprendió esto en su sesión 15 y dejó escrito que las claves de volumen
son *load-bearing*: las mantuvo idénticas a través del renombrado justamente
para que el corpus ya ingestado sobreviviera. Acá la conclusión es la misma con
una decisión distinta: **el compose se queda en la raíz**. Es además donde lo
tiene el curso.

### 3. El validador de specs

`scripts/validate_specs.py` hace `REPO_ROOT = Path(__file__).parent.parent` y
después busca `REPO_ROOT / "openspec"`. Movido a `ai-service/scripts/`,
`REPO_ROOT` sería `ai-service/` y no encontraría nada que validar.

Podría arreglarse con un `parents[2]`, pero eso sería atar un script del repo a
vivir dentro de una de sus apps. `openspec/` documenta las dos; su validador
pertenece al mismo nivel. Se queda en la raíz, y es el único archivo de
`scripts/` que no se mueve.

Su otra propiedad se vuelve útil justo acá: es stdlib puro, sin dependencias,
así que corre con `python scripts/validate_specs.py` desde la raíz, sin
necesidad de un `pyproject.toml` al lado ni de `uv`. Esa decisión se tomó para
que cualquier harness y CI lo corrieran igual; sirve además para que sobreviva
a esta mudanza.

## Por qué las specs siguen diciendo `app/generation/rag/...`

10 de las 11 specs nombran rutas de código: 25 menciones. La opción obvia es
prefijarlas todas con `ai-service/`.

No se hace, y el precedente es del propio curso: cuando la sesión 15 renombró
`estimator/` a `ai-service/`, dejó escrito que la raíz del paquete Python sigue
siendo `app.*` y que eso **no** hay que "arreglarlo". El directorio cambió; el
vocabulario con el que se habla del código, no.

Acá aplica igual, y con dos razones propias:

- **Ganancia de información: cero.** `app/generation/rag/chunking/functional_spec.py`
  identifica el archivo sin ambigüedad, antes y después.
- **Riesgo de la edición: no cero.** Un reemplazo masivo sobre 11 archivos de
  prosa técnica toca texto que no es una ruta (`app` aparece también como
  palabra) y ensucia el diff de un cambio que se propuso como mecánico.

En su lugar, una línea en `openspec/project.md` declara la base: *las rutas de
código en las specs del servicio IA son relativas a `ai-service/`*. Una regla,
un lugar, en vez de 25 prefijos que hay que mantener sincronizados.

Cuándo deja de valer: el día que una spec describa código de
`business-backend/`, esa spec nombra su ruta completa desde la raíz. La regla
cubre las specs del servicio IA, no todas.

## Qué NO se automatiza

`data/`, `.env` y `.venv/` están gitignoreados, así que `git mv` no los ve y un
`git status` limpio después de la mudanza **no prueba** que estén en su lugar.
Los tres se mueven a mano y se verifican corriendo la suite: los tests que leen
`data/policies/` fallan por archivo faltante si `data/` quedó atrás, y ese es el
chequeo. `.venv/` en realidad no se mueve: se descarta y se regenera con
`uv sync` desde `ai-service/`, que es más barato que mover un entorno virtual
con rutas absolutas adentro.

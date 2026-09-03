# Visual Time RAG

Proyecto final del Master en AI Engineering (lidr). Un RAG sobre la
documentación funcional del sistema **Visual Time** (seguros): 2.169 documentos
de especificación, uno por transacción, troceados, embebidos e indexados en
pgvector para poder preguntarles en lenguaje natural.

Monorepo de dos proyectos, el layout que fija el programa:

| | qué es | estado |
|---|---|---|
| [`ai-service/`](ai-service/README.md) | el servicio Python + FastAPI: ingesta, chunking, embeddings, recuperación | construido |
| `business-backend/` | el frontend y backend de negocio | propuesto, ver [`openspec/changes/add-web-console/`](openspec/changes/add-web-console/proposal.md) |

## Empezar

```bash
cd ai-service
uv sync
cp .env.example .env      # completar si vas a usar embeddings o el reranker
uv run pytest
```

El detalle de todo lo demás —el pipeline del corpus, la persistencia en
pgvector, el mapa de procesos, las evaluaciones— está en el
[README del servicio](ai-service/README.md).

Postgres con pgvector para desarrollo local sale del compose de la raíz:

```bash
docker compose up -d
```

Vive acá y no dentro de `ai-service/` a propósito: el nombre del proyecto de
compose sale del directorio donde está el archivo, así que moverlo renombraría
el volumen y levantaría una base vacía sin decir nada.

## Los datos NO están en el repo

`ai-service/data/` está gitignoreado. Contiene documentación funcional y un
export de una tabla de producción que **pertenecen a un cliente**, más el
corpus generado. El repo trae el pipeline, no los datos.

## Fuente de verdad

Este repo documenta su comportamiento con
[OpenSpec](https://github.com/Fission-AI/OpenSpec):

- **`openspec/specs/<capability>/spec.md`** — qué hace el sistema **hoy**. Es
  normativo: si el código y la spec no coinciden, uno de los dos tiene un bug.
- **`openspec/changes/`** — trabajo en curso; **`changes/archive/`** — por qué
  las cosas llegaron a ser como son.
- **`openspec/domain/`** — referencia sobre VisualTIME, el sistema fuente.
- **[`AGENTS.md`](AGENTS.md)** — el ciclo de trabajo, agnóstico de modelo y de
  harness. `CLAUDE.md` y cualquier otro archivo de harness son punteros a ese.

```bash
python scripts/validate_specs.py   # valida el formato de specs y changes
```

Corre desde la raíz y sin `uv`: es stdlib puro, para que cualquier harness y CI
lo corran igual.

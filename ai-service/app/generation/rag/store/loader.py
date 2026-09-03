"""Bulk load: corpus JSON plus vector sidecar into Postgres, by ``COPY``.

57131 rows of 1536 floats through ``session.add_all()`` builds 57131 ORM
objects, tracks them in the identity map and emits that many INSERTs. The ORM
defines the schema and answers the queries; moving the bulk is the driver's job.

``COPY`` goes into a temporary table and from there into the real one with
``ON CONFLICT DO UPDATE`` on the metadata columns. Copying straight into the
final table would be one step shorter but ``COPY`` has no conflict clause.

Idempotent in the sense that matters -- the row COUNT does not grow -- but NOT
blind to metadata: a second run rewrites the metadata columns of every row it
sees. ``DO NOTHING`` was blind, and adding `window_type_name` to 46613 chunks
under it would have inserted nothing and left the column null. The embedding is
never rewritten: it is tied to the text, and if the text changed then so did
``content_hash`` and this is a new row rather than a conflict.

|| Carga masiva: corpus JSON más el sidecar de vectores a Postgres, por ``COPY``.

57131 filas de 1536 floats por ``session.add_all()`` construye 57131 objetos
ORM, los rastrea en la identity map y emite esa cantidad de INSERTs. El ORM
define el esquema y responde las consultas; mover el bulto es del driver.

``COPY`` va a una tabla temporal y de ahí a la real con ``ON CONFLICT DO
UPDATE`` sobre las columnas de metadata. Copiar directo a la tabla final sería un
paso menos, pero ``COPY`` no tiene cláusula de conflicto.

Idempotente en el sentido que importa —el CONTEO de filas no crece— pero NO
ciega a la metadata: una segunda corrida reescribe las columnas de metadata de
cada fila que ve. ``DO NOTHING`` era ciega, y agregar `window_type_name` a 46613
chunks con ella no habría insertado nada y habría dejado la columna en null. El
embedding nunca se reescribe: está atado al texto, y si el texto cambió entonces
cambió el ``content_hash`` y esto es una fila nueva y no un conflicto.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import structlog

from app.generation.rag.embedding.sidecar import load_sidecar, rows_by_hash

logger = structlog.get_logger(__name__)

# The order COPY writes and the temporary table declares. One list, used by
# both, so they cannot drift apart.
# || El orden en que COPY escribe y en que se declara la tabla temporal. Una
# sola lista, usada por los dos, así no se pueden desalinear.
COPY_COLUMNS = (
    "tenant_id",
    "doc_version",
    "content_hash",
    "source_type",
    "chunk_id",
    "document_id",
    "document_title",
    "text",
    "embedding",
    "token_count",
    "chunk_type",
    "section",
    "bullet_path",
    "field",
    "transaction_type",
    "document_kind",
    "module_code",
    "module_name",
    "submodule_code",
    "submodule_name",
    "window_type_name",
)


def format_vector(values: np.ndarray) -> str:
    """pgvector's text input format: ``[0.1,0.2,...]``.

    || El formato de entrada de texto de pgvector: ``[0.1,0.2,...]``.
    """
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def iter_rows(
    corpus_path: Path, embeddings_root: Path
) -> tuple[str, list[tuple], list[str]]:
    """Join one module's chunks to their vectors by ``content_hash``.

    A chunk with no vector is NOT loaded and IS reported. Inventing a zero
    vector would index it where nothing ever matches -- the silent failure the
    embedding layer already refuses.

    || Une los chunks de un módulo con sus vectores por ``content_hash``. Un
    chunk sin vector NO se carga y SÍ se reporta. Inventarle un vector en cero
    lo indexaría donde nada matchea nunca — el fallo silencioso que la capa de
    embeddings ya rechaza.
    """
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    module = payload["module"]

    vectors, index = load_sidecar(embeddings_root, module)
    by_hash = rows_by_hash(index)

    rows: list[tuple] = []
    without_vector: list[str] = []
    for document in payload["documents"]:
        for chunk in document["chunks"]:
            metadata = chunk["metadata"]
            row_number = by_hash.get(metadata["content_hash"])
            if row_number is None or vectors is None:
                without_vector.append(chunk["chunk_id"])
                continue
            rows.append(
                (
                    metadata["tenant_id"],
                    metadata["doc_version"],
                    metadata["content_hash"],
                    metadata.get("source_type", "functional_spec"),
                    chunk["chunk_id"],
                    document["document_id"],
                    document.get("document_title"),
                    chunk["text"],
                    format_vector(vectors[row_number]),
                    chunk["token_count"],
                    metadata["chunk_type"],
                    metadata.get("section"),
                    metadata.get("bullet_path"),
                    metadata.get("field"),
                    metadata.get("transaction_type"),
                    metadata.get("document_kind"),
                    metadata.get("module_code"),
                    metadata.get("module_name"),
                    metadata.get("submodule_code"),
                    metadata.get("submodule_name"),
                    metadata.get("window_type_name"),
                )
            )
    return module, rows, without_vector


# The temporary table mirrors COPY_COLUMNS exactly. `text` and `vector` with no
# length limits: this table is a landing strip, and every constraint worth
# having is on the real table.
# || La tabla temporal espeja COPY_COLUMNS exactamente. `text` y `vector` sin
# límites: esta tabla es una pista de aterrizaje, y toda restricción que valga
# la pena está en la tabla real.
_TEMP_TABLE_DDL = """
CREATE TEMPORARY TABLE chunks_staging (
    tenant_id text, doc_version text, content_hash text, source_type text,
    chunk_id text, document_id text, document_title text,
    text text, embedding vector({dimensions}), token_count integer,
    chunk_type text, section text, bullet_path text, field text,
    transaction_type text, document_kind text,
    module_code text, module_name text, submodule_code text, submodule_name text,
    window_type_name text
) ON COMMIT DROP
"""

# Rows of this corpus whose content_hash is no longer anywhere in it. The
# store's counterpart of the sidecar's "dropped": without it, regenerating the
# corpus in place leaves rows pointing at text that no longer exists and
# retrieval keeps returning them.
#
# Scoped to the WHOLE corpus, never to one module: a module's staging table
# knows nothing about the other 27, so pruning per module would delete them.
# || Filas de este corpus cuyo content_hash ya no esta en ninguna parte de el.
# El equivalente en el store del "descartadas" del sidecar: sin esto, regenerar
# el corpus en el lugar deja filas que apuntan a texto que ya no existe y la
# recuperacion las sigue devolviendo.
#
# Es del corpus ENTERO, nunca de un modulo: la staging de un modulo no sabe nada
# de los otros 27, asi que podar por modulo los borraria.
_PRUNE_DDL = "CREATE TEMPORARY TABLE corpus_hashes (content_hash text PRIMARY KEY) ON COMMIT DROP"

_PRUNE_SQL = """
DELETE FROM chunks
WHERE tenant_id = %s AND doc_version = %s
  AND content_hash NOT IN (SELECT content_hash FROM corpus_hashes)
"""

# The metadata columns, which are everything that is NOT the row's identity and
# NOT the embedded text. A change in any of these has to reach an existing row:
# `DO NOTHING` made the load idempotent on content and silently blind to
# metadata, so adding `window_type_name` to 46613 chunks would have inserted
# nothing and left the column null.
# || Las columnas de metadata, que son todo lo que NO es la identidad de la fila
# ni el texto embebido. Un cambio en cualquiera de estas tiene que llegar a una
# fila existente: `DO NOTHING` hacia la carga idempotente en contenido y ciega a
# la metadata, asi que agregar `window_type_name` a 46613 chunks no habria
# insertado nada y habria dejado la columna en null.
_METADATA_COLUMNS = (
    "chunk_id",
    "document_id",
    "document_title",
    "chunk_type",
    "section",
    "bullet_path",
    "field",
    "transaction_type",
    "document_kind",
    "module_code",
    "module_name",
    "submodule_code",
    "submodule_name",
    "window_type_name",
)

# The embedding is NOT refreshed: it is tied to the text, and the text is what
# `content_hash` covers. If the text changed, the hash changed, and this is a
# new row rather than a conflict.
# || El embedding NO se refresca: esta atado al texto, y el texto es lo que cubre
# `content_hash`. Si el texto cambio, cambio el hash, y esto es una fila nueva y
# no un conflicto.
# DISTINCT ON is required, not cosmetic: `ON CONFLICT DO UPDATE` refuses to
# affect the same target row twice in one command, and the staging table has
# 5127 duplicate hashes -- a repeated text is a repeated hash by construction.
# `DO NOTHING` tolerated that silently; `DO UPDATE` raises CardinalityViolation.
# || El DISTINCT ON es necesario, no cosmetico: `ON CONFLICT DO UPDATE` se niega
# a afectar la misma fila destino dos veces en un comando, y la staging tiene
# 5127 hashes duplicados — un texto repetido es un hash repetido por
# construccion. `DO NOTHING` lo toleraba en silencio; `DO UPDATE` levanta
# CardinalityViolation.
_INSERT_SQL = """
INSERT INTO chunks ({columns})
SELECT DISTINCT ON (tenant_id, doc_version, source_type, content_hash) {columns}
FROM chunks_staging
ORDER BY tenant_id, doc_version, source_type, content_hash, chunk_id
ON CONFLICT (tenant_id, doc_version, source_type, content_hash) DO UPDATE SET
{updates}
"""


def prune_corpus(
    connection, tenant_id: str, doc_version: str, corpus_hashes: set[str]
) -> int:
    """Delete this corpus's rows whose text is no longer in it.

    Takes the hashes of the ENTIRE corpus, so it can only be called once every
    module has been read. Called with a partial set it would delete real rows.

    || Borra las filas de este corpus cuyo texto ya no esta en el. Recibe los
    hashes del corpus ENTERO, asi que solo puede llamarse una vez leidos todos
    los modulos. Llamada con un conjunto parcial borraria filas reales.
    """
    with connection.cursor() as cursor:
        cursor.execute(_PRUNE_DDL)
        with cursor.copy("COPY corpus_hashes (content_hash) FROM STDIN") as copy:
            for content_hash in corpus_hashes:
                copy.write_row((content_hash,))
        cursor.execute(_PRUNE_SQL, (tenant_id, doc_version))
        return cursor.rowcount


def load_module(connection, rows: list[tuple], *, dimensions: int) -> tuple[int, int]:
    """``COPY`` into a staging table, then write. Returns ``(copied, written)``.

    Takes a raw psycopg connection, not a Session: this is the one path that
    deliberately goes around the ORM.

    || ``COPY`` a una tabla de staging y después inserta lo que no está. Recibe
    una conexión cruda de psycopg, no una Session: este es el único camino que
    a propósito esquiva el ORM.
    """
    if not rows:
        return 0, 0

    columns = ", ".join(COPY_COLUMNS)
    with connection.cursor() as cursor:
        cursor.execute(_TEMP_TABLE_DDL.format(dimensions=dimensions))
        copy_sql = f"COPY chunks_staging ({columns}) FROM STDIN"
        with cursor.copy(copy_sql) as copy:
            for row in rows:
                copy.write_row(row)
        updates = ",\n".join(f"    {name} = EXCLUDED.{name}" for name in _METADATA_COLUMNS)
        cursor.execute(_INSERT_SQL.format(columns=columns, updates=updates))
        # rowcount counts inserts AND updates, so this is "rows written", never
        # "rows inserted". Naming it honestly matters: a second run over an
        # unchanged corpus now writes every row (refreshing metadata to the same
        # values) instead of writing none.
        # || rowcount cuenta inserts Y updates, asi que esto es "filas escritas"
        # y nunca "filas insertadas". Nombrarlo con honestidad importa: una
        # segunda corrida sobre un corpus sin cambios ahora escribe todas las
        # filas (refrescando la metadata a los mismos valores) en vez de ninguna.
        written = cursor.rowcount
    return len(rows), written

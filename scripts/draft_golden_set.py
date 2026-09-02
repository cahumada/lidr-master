"""Draft a golden set for retrieval evaluation, derived from the corpus itself.

A golden set written by the same system that is then evaluated against it does
not measure anything: it measures whether the system agrees with itself. So every
question here is derived from a criterion that can be **re-checked with a query**,
and every one carries that criterion in its ``provenance`` field.

The output is marked ``PENDING_REVIEW`` and the evaluation repeats that mark until
somebody who knows the business confirms two things per question: that a user
would actually ask it, and that the annotated documents are the ones that answer
it.

Usage:
    uv run python scripts/draft_golden_set.py

|| Borradorea un golden set para evaluar la recuperación, derivado del corpus.

Un golden set escrito por el mismo sistema que después se evalúa contra él no
mide nada: mide si el sistema coincide consigo mismo. Así que cada pregunta acá
sale de un criterio que se puede **volver a chequear con una consulta**, y cada
una lleva ese criterio en su campo ``provenance``.

La salida queda marcada ``PENDING_REVIEW`` y la evaluación repite esa marca hasta
que alguien que conozca el negocio confirme dos cosas por pregunta: que un
usuario la haría, y que los documentos anotados son los que la responden.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.config import get_settings
from app.foundation.persistence.database import get_async_session_factory

OUTPUT = Path("evals/golden_retrieval.json")

# --- Type A: declared execution precedence -----------------------------------
# The best-grounded questions in the set. The corpus SAYS "this process requires
# that these be run first", so the relevant documents are the chain plus the
# process itself -- nothing inferred.
# || Las preguntas mejor fundadas del conjunto. El corpus DICE "este proceso
# requiere que estos se ejecuten antes", así que los documentos relevantes son la
# cadena más el proceso mismo — nada inferido.
_PRECEDENCE_SQL = """
SELECT e.source, string_agg(e.target, ',' ORDER BY e.target) AS targets,
       (SELECT max(document_title) FROM chunks c
        WHERE c.document_id = e.source AND c.tenant_id = :tenant) AS title
FROM process_map_edges e
WHERE e.tenant_id = :tenant AND e.doc_version = :version AND e.edge_type = 'requires'
GROUP BY e.source HAVING count(*) >= 2
ORDER BY count(*) DESC, e.source
"""

# Distractors for a precedence question: documents of the SAME module family
# (same code prefix) that are verifiably NOT in the declared chain. Similar
# enough to be tempting, and wrong.
# || Distractores para una pregunta de precedencia: documentos de la MISMA
# familia de módulo (mismo prefijo de código) que verificablemente NO están en
# la cadena declarada. Parecidos como para tentar, y equivocados.
_SIBLINGS_SQL = """
SELECT DISTINCT document_id FROM chunks
WHERE tenant_id = :tenant AND doc_version = :version
  AND document_id LIKE :prefix AND document_id <> ALL(:exclude)
ORDER BY document_id LIMIT 4
"""

# --- Type B: a field several documents validate ------------------------------
_FIELD_SQL = """
SELECT field, count(DISTINCT document_id) AS documents,
       string_agg(DISTINCT document_id, ',') AS ids
FROM chunks
WHERE tenant_id = :tenant AND doc_version = :version
  AND field IS NOT NULL AND lower(section) LIKE 'validacion%'
GROUP BY field HAVING count(DISTINCT document_id) BETWEEN 3 AND 8
ORDER BY count(DISTINCT document_id) DESC, field
LIMIT 6
"""

# Distractors for a field question: documents that validate a DIFFERENT field
# whose name shares a word. "Fecha Inicial" against "Fecha del proceso".
# || Distractores para una pregunta de campo: documentos que validan OTRO campo
# cuyo nombre comparte una palabra.
_NEAR_FIELD_SQL = """
SELECT DISTINCT document_id FROM chunks
WHERE tenant_id = :tenant AND doc_version = :version
  AND lower(section) LIKE 'validacion%'
  AND field IS NOT NULL AND field <> :field
  AND lower(field) LIKE :like
  AND document_id <> ALL(:exclude)
ORDER BY document_id LIMIT 4
"""

# --- Type C: asked by code ---------------------------------------------------
# One relevant document by construction. Included because it is how users
# actually talk about these transactions, and because it is the case the vector
# branch cannot answer at all.
# || Un solo documento relevante por construcción. Se incluye porque es como los
# usuarios hablan de estas transacciones, y porque es el caso que la rama
# vectorial no puede responder.
_BY_CODE_SQL = """
SELECT DISTINCT document_id, document_title, transaction_type
FROM chunks
WHERE tenant_id = :tenant AND doc_version = :version
  AND document_title IS NOT NULL AND length(document_title) BETWEEN 15 AND 60
  AND transaction_type IN ('functional_abm', 'query', 'process_report')
ORDER BY document_id
LIMIT 400
"""


def _prefix_of(code: str) -> str:
    """The module family of a code: the letters before its digits.

    || La familia de módulo de un código: las letras antes de sus dígitos.
    """
    letters = ""
    for char in code:
        if char.isdigit():
            break
        letters += char
    return letters or code[:3]


async def build(session, tenant: str, version: str) -> list[dict]:
    params = {"tenant": tenant, "version": version}
    questions: list[dict] = []

    # --- A: precedence -------------------------------------------------------
    for row in (await session.execute(text(_PRECEDENCE_SQL), params)).all():
        chain = row.targets.split(",")
        relevant = [row.source, *chain]
        siblings = (
            await session.execute(
                text(_SIBLINGS_SQL),
                {**params, "prefix": f"{_prefix_of(row.source)}%", "exclude": relevant},
            )
        ).scalars().all()
        title = (row.title or row.source).strip()
        questions.append(
            {
                "id": f"A-{row.source}",
                "type": "declared_precedence",
                "question": f"¿Qué procesos hay que ejecutar antes de {title} ({row.source})?",
                "relevant_document_ids": relevant,
                "distractor_document_ids": list(siblings),
                "provenance": (
                    f"El documento {row.source} declara en su sección Requisitos que requiere "
                    f"la ejecución previa de {', '.join(chain)}. Relevantes = el proceso más su "
                    f"cadena declarada. Distractores = documentos de la familia "
                    f"{_prefix_of(row.source)} que NO están en la cadena."
                ),
                "review": {"question_is_realistic": None, "annotation_is_correct": None},
            }
        )

    # --- B: a field several documents validate --------------------------------
    for row in (await session.execute(text(_FIELD_SQL), params)).all():
        relevant = sorted(row.ids.split(","))
        first_word = row.field.split()[0].lower()
        near = (
            await session.execute(
                text(_NEAR_FIELD_SQL),
                {**params, "field": row.field, "like": f"%{first_word}%", "exclude": relevant},
            )
        ).scalars().all()
        questions.append(
            {
                "id": f"B-{row.field.replace(' ', '_')}",
                "type": "field_validations",
                "question": f"¿Qué validaciones existen sobre el campo {row.field}?",
                "relevant_document_ids": relevant,
                "distractor_document_ids": list(near),
                "provenance": (
                    f"Relevantes = los {row.documents} documentos con un chunk de Validaciones "
                    f"cuyo metadata.field es exactamente '{row.field}'. Distractores = documentos "
                    f"que validan OTRO campo cuyo nombre contiene '{first_word}'."
                ),
                "review": {"question_is_realistic": None, "annotation_is_correct": None},
            }
        )

    # --- C: asked by code -----------------------------------------------------
    candidates = (await session.execute(text(_BY_CODE_SQL), params)).all()
    # Spread across transaction types instead of taking the first N, which would
    # all be from the same module.
    # || Repartidas entre tipos de transacción en vez de tomar las primeras N,
    # que serían todas del mismo módulo.
    by_type: dict[str, list] = {}
    for row in candidates:
        by_type.setdefault(row.transaction_type, []).append(row)
    for transaction_type, rows in by_type.items():
        for row in rows[:: max(1, len(rows) // 2)][:2]:
            prefix = _prefix_of(row.document_id)
            siblings = (
                await session.execute(
                    text(_SIBLINGS_SQL),
                    {**params, "prefix": f"{prefix}%", "exclude": [row.document_id]},
                )
            ).scalars().all()
            questions.append(
                {
                    "id": f"C-{row.document_id}",
                    "type": "by_code",
                    "question": f"¿Qué hace {row.document_id}?",
                    "relevant_document_ids": [row.document_id],
                    "distractor_document_ids": list(siblings),
                    "provenance": (
                        f"Relevante = el documento {row.document_id} ('{row.document_title}', "
                        f"tipo {transaction_type}). Un solo relevante por construcción: la "
                        f"pregunta nombra un código. Distractores = documentos de la familia "
                        f"{prefix}."
                    ),
                    "review": {"question_is_realistic": None, "annotation_is_correct": None},
                }
            )

    return questions


async def run() -> int:
    settings = get_settings()
    async with get_async_session_factory()() as session:
        questions = await build(session, settings.TENANT_ID, settings.DOC_VERSION)

    if not questions:
        print("No material found. Is the corpus loaded and the map built?", file=sys.stderr)
        return 1

    payload = {
        "status": "PENDING_REVIEW",
        "description": (
            "Borrador de golden set para evaluar la recuperación, DERIVADO DEL CORPUS y "
            "PENDIENTE DE REVISIÓN. Cada pregunta lleva en `provenance` el criterio "
            "verificable del que salió, y en `review` dos casillas que alguien que conozca "
            "el negocio tiene que completar: si un usuario haría esa pregunta, y si los "
            "documentos anotados son los que la responden. Hasta que estén completas, "
            "cualquier número medido contra esto NO es la calidad del sistema."
        ),
        "how_to_review": [
            "Por cada pregunta, poner review.question_is_realistic en true o false.",
            "Por cada pregunta, poner review.annotation_is_correct en true o false.",
            (
                "Si la anotación está incompleta, agregar los ids que falten a "
                "relevant_document_ids."
            ),
            (
                "Una pregunta con question_is_realistic en false se saca del conjunto, no "
                "se corrige: si nadie la haría, medirla no informa nada."
            ),
            (
                "FALTA UN TIPO DE PREGUNTA, y sesga la métrica. Las 22 de acá se derivan "
                "de criterios que naturalmente dan varios documentos relevantes, así que "
                "el conjunto premia traer MUCHOS documentos. No hay ninguna pregunta "
                "profunda sobre un solo documento —del estilo 'qué pasa si el importe de "
                "ajuste supera la comisión neta', cuya respuesta correcta son varios "
                "chunks de AGL009 y de nadie más—. Sin ese tipo, la medición favorece "
                "recortar a un chunk por documento y no se puede ver lo que ese recorte "
                "rompe. Agregar 4-6 de esas preguntas es lo más valioso que se le puede "
                "hacer a este conjunto."
            ),
        ],
        "what_the_types_mean": {
            "declared_precedence": "El corpus declara la dependencia. Es el tipo mejor fundado.",
            "field_validations": (
                "Relevancia por metadata.field exacto. Ojo: favorece a la búsqueda léxica, "
                "porque el nombre del campo aparece literalmente en el texto."
            ),
            "by_code": (
                "Un solo relevante. Es el caso que la búsqueda vectorial no puede responder "
                "y por el que existe la rama exacta."
            ),
        },
        "questions": questions,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    counts: dict[str, int] = {}
    for question in questions:
        counts[question["type"]] = counts.get(question["type"], 0) + 1
    print(f"Wrote {OUTPUT} — {len(questions)} preguntas, PENDING_REVIEW")
    for kind, count in sorted(counts.items()):
        print(f"  {kind:<22}{count:>3}")
    relevant = sum(len(q["relevant_document_ids"]) for q in questions)
    distractors = sum(len(q["distractor_document_ids"]) for q in questions)
    print(f"  {'relevantes anotados':<22}{relevant:>3}")
    print(f"  {'distractores':<22}{distractors:>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

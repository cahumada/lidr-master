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
    uv run python scripts/draft_golden_set.py --module policies --module claims

|| Borradorea un golden set para evaluar la recuperacion, derivado del corpus.

Un golden set escrito por el mismo sistema que despues se evalua contra el no
mide nada: mide si el sistema coincide consigo mismo. Asi que cada pregunta aca
sale de un criterio que se puede **volver a chequear con una consulta**, y cada
una lleva ese criterio en su campo ``provenance``.

La salida queda marcada ``PENDING_REVIEW`` y la evaluacion repite esa marca hasta
que alguien que conozca el negocio confirme dos cosas por pregunta: que un
usuario la haria, y que los documentos anotados son los que la responden.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), asi que se agrega la raiz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.config import get_settings
from app.foundation.persistence.database import get_async_session_factory

OUTPUT = Path("evals/golden_retrieval.json")
CHUNKS_DIR = Path("data/chunks")

# Human-authored questions, merged in and never overwritten. They live in their
# own file because regenerating the draft would wipe them, and they are the most
# valuable questions in the set: real user questions with a human annotation.
# || Preguntas escritas por una persona, que se mezclan y nunca se sobreescriben.
# Viven en su propio archivo porque regenerar el borrador las borraria, y son las
# mas valiosas del conjunto: preguntas reales de usuario con anotacion humana.
CURATED = Path("evals/golden_curated.json")

# The modules the golden set focuses on: the core of the business.
# || Los modulos en los que se enfoca el golden set: el nucleo del negocio.
FOCUS_MODULES = ("policies", "claims", "collections", "designer")

MODULE_LABELS = {
    "policies": "Polizas",
    "claims": "Siniestros",
    "collections": "Cobranzas",
    "designer": "Disenador",
}

# How many questions of each derivable type per module. Balanced on purpose: the
# first draft let the material decide and came out 27% reinsurance -- a module of
# 36 documents out of 2211 -- because it is the one that declares the most
# execution precedence.
# || Cuantas preguntas de cada tipo derivable por modulo. Balanceado a proposito:
# el primer borrador dejo que el material decidiera y salio 27% reaseguros, un
# modulo de 36 documentos sobre 2211, porque es el que mas precedencia declara.
PER_MODULE = {"field_validations": 4, "by_code": 3}

_PRECEDENCE_SQL = """
SELECT e.source, string_agg(e.target, ',' ORDER BY e.target) AS targets,
       (SELECT max(document_title) FROM chunks c
        WHERE c.document_id = e.source AND c.tenant_id = :tenant) AS title
FROM process_map_edges e
WHERE e.tenant_id = :tenant AND e.doc_version = :version AND e.edge_type = 'requires'
GROUP BY e.source HAVING count(*) >= 2
ORDER BY count(*) DESC, e.source
"""

# Distractors: documents of the SAME module family (same code prefix) that are
# verifiably NOT relevant. Similar enough to be tempting, and wrong.
# || Distractores: documentos de la MISMA familia de modulo (mismo prefijo de
# codigo) que verificablemente NO son relevantes. Parecidos como para tentar, y
# equivocados.
_SIBLINGS_SQL = """
SELECT DISTINCT document_id FROM chunks
WHERE tenant_id = :tenant AND doc_version = :version
  AND document_id LIKE :prefix AND document_id <> ALL(:exclude)
ORDER BY document_id LIMIT 4
"""

# Field and document, ungrouped: the grouping has to happen per corpus module,
# and the corpus module is not a column in the table.
# || Campo y documento, sin agrupar: la agrupacion tiene que ser por modulo del
# corpus, y el modulo del corpus no es una columna de la tabla.
_FIELD_ROWS_SQL = """
SELECT DISTINCT field, document_id
FROM chunks
WHERE tenant_id = :tenant AND doc_version = :version
  AND field IS NOT NULL AND lower(section) LIKE 'validacion%'
"""

_NEAR_FIELD_SQL = """
SELECT DISTINCT document_id FROM chunks
WHERE tenant_id = :tenant AND doc_version = :version
  AND lower(section) LIKE 'validacion%'
  AND field IS NOT NULL AND field <> :field
  AND lower(field) LIKE :like
  AND document_id <> ALL(:exclude)
ORDER BY document_id LIMIT 6
"""

_BY_CODE_SQL = """
SELECT DISTINCT document_id, document_title, transaction_type
FROM chunks
WHERE tenant_id = :tenant AND doc_version = :version
  AND document_title IS NOT NULL AND length(document_title) BETWEEN 15 AND 60
  AND transaction_type IS NOT NULL AND transaction_type <> 'unknown'
ORDER BY document_id
"""


def corpus_module_map(chunks_dir: Path, modules) -> dict[str, str]:
    """Which corpus module each document came from.

    The corpus module -- the JSON the document was chunked into -- and NOT the
    breadcrumb's ``module_name``. The breadcrumb resolves for 54% of the corpus,
    so filtering by it would miss 75 of the 127 ``claims`` documents and 106 of
    the 134 ``designer`` ones: exactly two of the four modules in focus.

    || El modulo del corpus —el JSON en el que se troceo el documento— y NO el
    ``module_name`` del breadcrumb. El breadcrumb resuelve para el 54% del
    corpus, asi que filtrar por el se perderia 75 de los 127 documentos de
    ``claims`` y 106 de los 134 de ``designer``: justo dos de los cuatro modulos
    en foco.
    """
    mapping: dict[str, str] = {}
    for module in modules:
        path = chunks_dir / f"{module}.json"
        if not path.exists():
            continue
        for document in json.loads(path.read_text(encoding="utf-8"))["documents"]:
            if document["chunks"]:
                mapping[document["document_id"].upper()] = module
    return mapping


def _prefix_of(code: str) -> str:
    """The module family of a code: the letters before its digits.

    || La familia de modulo de un codigo: las letras antes de sus digitos.
    """
    letters = ""
    for char in code:
        if char.isdigit():
            break
        letters += char
    return letters or code[:3]


def _review() -> dict:
    return {"question_is_realistic": None, "annotation_is_correct": None}


async def build(session, tenant: str, version: str, modules) -> tuple[list[dict], dict]:
    """Questions balanced across the modules in focus.

    Driven by module and not by material: letting the material decide is what
    produced a first draft that was 27% reinsurance.

    || Preguntas balanceadas entre los modulos en foco. Manejado por modulo y no
    por el material: dejar que el material decida es lo que produjo un primer
    borrador 27% reaseguros.
    """
    params = {"tenant": tenant, "version": version}
    module_of = corpus_module_map(CHUNKS_DIR, modules)
    in_focus = set(module_of)
    questions: list[dict] = []

    def label(module: str) -> str:
        return MODULE_LABELS.get(module, module)

    # --- A: declared precedence, only where it exists ---------------------------
    # Barely exists in these modules: the declarations live in the reinsurance and
    # solvency-margin batch processes. Counted and reported rather than padded
    # with questions from modules nobody asked for.
    # || Casi no existe en estos modulos: las declaraciones viven en los procesos
    # batch de reaseguros y margen de solvencia. Se cuenta y se reporta en vez de
    # rellenar con preguntas de modulos que nadie pidio.
    precedence_by_module: dict[str, int] = {}
    for row in (await session.execute(text(_PRECEDENCE_SQL), params)).all():
        module = module_of.get(row.source.upper())
        if module is None:
            continue
        precedence_by_module[module] = precedence_by_module.get(module, 0) + 1
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
                "module": module,
                "type": "declared_precedence",
                "question": f"Que procesos hay que ejecutar antes de {title} ({row.source})?",
                "relevant_document_ids": relevant,
                "distractor_document_ids": list(siblings),
                "provenance": (
                    f"[{label(module)}] {row.source} declara en su seccion Requisitos que "
                    f"requiere la ejecucion previa de {', '.join(chain)}. Relevantes = el "
                    f"proceso mas su cadena declarada. Distractores = documentos de la "
                    f"familia {_prefix_of(row.source)} que NO estan en la cadena."
                ),
                "review": _review(),
            }
        )

    field_rows = (await session.execute(text(_FIELD_ROWS_SQL), params)).all()
    code_rows = (await session.execute(text(_BY_CODE_SQL), params)).all()

    for module in modules:
        module_docs = {d for d, m in module_of.items() if m == module}

        # --- B: a field several documents of THIS module validate ---------------
        by_field: dict[str, set[str]] = {}
        for row in field_rows:
            if row.document_id.upper() in module_docs:
                by_field.setdefault(row.field, set()).add(row.document_id)
        eligible = sorted(
            ((f, sorted(d)) for f, d in by_field.items() if f.strip() and 3 <= len(d) <= 8),
            key=lambda item: (-len(item[1]), item[0]),
        )
        for field, relevant in eligible[: PER_MODULE["field_validations"]]:
            first_word = field.split()[0].lower()
            near = (
                await session.execute(
                    text(_NEAR_FIELD_SQL),
                    {**params, "field": field, "like": f"%{first_word}%", "exclude": relevant},
                )
            ).scalars().all()
            questions.append(
                {
                    "id": f"B-{module}-{field.replace(' ', '_')}",
                    "module": module,
                    "type": "field_validations",
                    "question": (
                        f"Que validaciones existen sobre el campo {field} en {label(module)}?"
                    ),
                    "relevant_document_ids": relevant,
                    # Distractors kept inside the focus modules: one from a module
                    # nobody asked about would be trivially wrong for the wrong
                    # reason.
                    # || Distractores dentro de los modulos en foco: uno de un
                    # modulo que nadie pidio seria trivialmente incorrecto por la
                    # razon equivocada.
                    "distractor_document_ids": [d for d in near if d.upper() in in_focus][:4],
                    "provenance": (
                        f"[{label(module)}] Relevantes = los {len(relevant)} documentos de "
                        f"{module} con un chunk de Validaciones cuyo metadata.field es "
                        f"exactamente '{field}'. Distractores = documentos que validan OTRO "
                        f"campo cuyo nombre contiene '{first_word}'."
                    ),
                    "review": _review(),
                }
            )

        # --- C: asked by code, spread across transaction types ------------------
        module_codes = [row for row in code_rows if row.document_id.upper() in module_docs]
        by_type: dict[str, list] = {}
        for row in module_codes:
            by_type.setdefault(row.transaction_type, []).append(row)
        # One from the middle of each type's list, so the pick is not all from the
        # alphabetical head of one family.
        # || Uno del medio de la lista de cada tipo, para que la eleccion no sea
        # toda de la cabeza alfabetica de una familia.
        picked = [rows[len(rows) // 2] for rows in by_type.values()]
        for row in picked[: PER_MODULE["by_code"]]:
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
                    "module": module,
                    "type": "by_code",
                    "question": f"Que hace {row.document_id}?",
                    "relevant_document_ids": [row.document_id],
                    "distractor_document_ids": list(siblings),
                    "provenance": (
                        f"[{label(module)}] Relevante = {row.document_id} "
                        f"('{row.document_title}', tipo {row.transaction_type}). Un solo "
                        f"relevante por construccion: la pregunta nombra un codigo. "
                        f"Distractores = documentos de la familia {prefix}."
                    ),
                    "review": _review(),
                }
            )

    return questions, {"precedence_available_by_module": precedence_by_module}


def load_curated() -> list[dict]:
    """The human-authored questions, or an empty list when there are none.

    || Las preguntas escritas por una persona, o lista vacia si no hay.
    """
    if not CURATED.exists():
        return []
    return json.loads(CURATED.read_text(encoding="utf-8"))["questions"]


def _payload(questions: list[dict], modules, notes: dict) -> dict:
    by_module: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for question in questions:
        by_module[question["module"]] = by_module.get(question["module"], 0) + 1
        by_type[question["type"]] = by_type.get(question["type"], 0) + 1

    return {
        # Mixed on purpose: the curated ones are reviewed, the drafted ones are
        # not. A single status would have to lie about one half.
        # || Mixto a proposito: las curadas estan revisadas y las borradoreadas
        # no. Un status unico tendria que mentir sobre una de las dos mitades.
        "status": "PARTIALLY_REVIEWED",
        "reviewed_questions": sum(
            1 for q in questions if q.get("review", {}).get("annotation_is_correct") is True
        ),
        "focus_modules": list(modules),
        "questions_by_module": by_module,
        "questions_by_type": by_type,
        "description": (
            "Borrador de golden set para evaluar la recuperacion, DERIVADO DEL CORPUS y "
            "PENDIENTE DE REVISION. Enfocado en los modulos del nucleo del negocio. Cada "
            "pregunta lleva en `provenance` el criterio verificable del que salio, y en "
            "`review` dos casillas que alguien que conozca el negocio tiene que completar: "
            "si un usuario haria esa pregunta, y si los documentos anotados son los que la "
            "responden. Hasta que esten completas, cualquier numero medido contra esto NO "
            "es la calidad del sistema."
        ),
        "how_to_review": [
            "Por cada pregunta, poner review.question_is_realistic en true o false.",
            "Por cada pregunta, poner review.annotation_is_correct en true o false.",
            (
                "Si la anotacion esta incompleta, agregar los ids que falten a "
                "relevant_document_ids."
            ),
            (
                "Una pregunta con question_is_realistic en false se saca del conjunto, no "
                "se corrige: si nadie la haria, medirla no informa nada."
            ),
            (
                "FALTA UN TIPO DE PREGUNTA, y sesga la metrica. Todas las de aca se derivan "
                "de criterios que dan varios documentos relevantes, asi que el conjunto "
                "premia traer MUCHOS documentos. No hay ninguna pregunta profunda sobre un "
                "solo documento —del estilo 'que pasa si el importe de ajuste supera la "
                "comision neta', cuya respuesta correcta son varios chunks de AGL009 y de "
                "nadie mas—. Peor: medirla necesitaria anotar CHUNKS relevantes y no "
                "documentos, porque precision@k por documento no puede expresar 'quiero "
                "varios chunks de este uno'. Es el trabajo mas valioso que le queda a este "
                "conjunto."
            ),
        ],
        "known_gaps": {
            "declared_precedence_scarce_here": (
                "Las cadenas de precedencia casi no existen en estos modulos: las "
                "declaraciones viven en los procesos batch de reaseguros y margen de "
                "solvencia. Disponibles por modulo en foco: "
                f"{notes.get('precedence_available_by_module', {})}."
            ),
            "no_deep_single_document_questions": (
                "Ver el ultimo punto de how_to_review. El conjunto no puede medir el caso "
                "en que la respuesta correcta son varios chunks de un solo documento."
            ),
            "corpus_module_is_not_in_the_store": (
                "El modulo del corpus (policies, claims, ...) es la unica agrupacion "
                "completa y no es una columna de la tabla `chunks`: el breadcrumb resuelve "
                "para el 54%. Este generador lo lee de los JSON del corpus; la recuperacion "
                "no puede filtrar por el."
            ),
        },
        "what_the_types_mean": {
            "declared_precedence": "El corpus declara la dependencia. Es el tipo mejor fundado.",
            "field_validations": (
                "Relevancia por metadata.field exacto. Ojo: favorece a la busqueda lexica, "
                "porque el nombre del campo aparece literalmente en el texto."
            ),
            "by_code": (
                "Un solo relevante. Es el caso que la busqueda vectorial no puede responder "
                "y por el que existe la rama exacta."
            ),
        },
        "questions": questions,
    }


async def run(modules) -> int:
    settings = get_settings()
    async with get_async_session_factory()() as session:
        questions, notes = await build(session, settings.TENANT_ID, settings.DOC_VERSION, modules)

    if not questions:
        print("No material found. Is the corpus loaded and the map built?", file=sys.stderr)
        return 1

    curated = load_curated()
    # Curated first: they are the ones a human vouched for, and reading the file
    # top-down should start with those.
    # || Las curadas primero: son las que una persona avalo, y leer el archivo de
    # arriba hacia abajo deberia empezar por esas.
    payload = _payload(curated + questions, modules, notes)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT} - {len(curated) + len(questions)} preguntas")
    print(f"  {len(curated):>3} escritas por una persona (evals/golden_curated.json), revisadas")
    print(f"  {len(questions):>3} borradoreadas del corpus, PENDIENTES DE REVISION\n")
    print("  por modulo:")
    for module, count in sorted(payload["questions_by_module"].items()):
        print(f"    {MODULE_LABELS.get(module, module):<14}{count:>3}")
    print("  por tipo:")
    for kind, count in sorted(payload["questions_by_type"].items()):
        print(f"    {kind:<22}{count:>3}")
    relevant = sum(len(q["relevant_document_ids"]) for q in questions)
    distractors = sum(len(q["distractor_document_ids"]) for q in questions)
    print(f"\n  relevantes anotados: {relevant}")
    print(f"  distractores:        {distractors}")
    print(f"  precedencia disponible por modulo: {notes['precedence_available_by_module']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module", action="append", default=None,
        help=f"Corpus modules to focus on (default: {', '.join(FOCUS_MODULES)}).",
    )
    args = parser.parse_args()
    return asyncio.run(run(tuple(args.module or FOCUS_MODULES)))


if __name__ == "__main__":
    raise SystemExit(main())

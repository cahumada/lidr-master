"""Evaluate retrieval against the golden set: precision@k and latency per config.

This is the number that gets reported, and it is what the course does
(``scripts/eval_retrieval_s10.py``): ``precision@k = hits / k``, per named
configuration, with latency alongside. It measures what matters -- of the k
chunks that will go into the generator's context, how many are useful.

``precision@k`` has a ceiling below 1 whenever a question has fewer than k
relevant documents: with 3 relevant and k=10 the best possible is 0.30. So the
ceiling is reported next to the score, because 0.28 out of a possible 0.30 and
0.28 out of a possible 1.00 are very different results and the bare number
cannot tell them apart.

Usage:
    docker compose up -d
    uv run python scripts/eval_retrieval.py
    uv run python scripts/eval_retrieval.py --k 5 --config fused

|| Evalúa la recuperación contra el golden set: precision@k y latencia por config.

Este es el número que se reporta, y es lo que hace el curso: ``precision@k =
hits / k``, por configuración con nombre, con la latencia al lado. Mide lo que
importa: de los k chunks que van a entrar al contexto del generador, cuántos
sirven.

``precision@k`` tiene un techo menor a 1 cuando una pregunta tiene menos de k
documentos relevantes: con 3 relevantes y k=10 lo mejor posible es 0,30. Así que
el techo se reporta al lado del puntaje, porque 0,28 sobre un techo de 0,30 y
0,28 sobre un techo de 1,00 son resultados muy distintos y el número solo no los
distingue.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.foundation.persistence.database import get_async_session_factory
from app.generation.rag.retrieval.hybrid import ALL_BRANCHES, DEFAULT_BRANCHES, HybridRetriever
from app.generation.rag.store.repository import ChunkRepository, SearchFilters

GOLDEN_PATH = Path("evals/golden_retrieval.json")
REPORT_PATH = Path("evals/RETRIEVAL_EVAL.md")

# The configurations compared, the way the course compares named stage configs.
# || Las configuraciones que se comparan, como el curso compara configuraciones
# de etapas con nombre.
# `cap` is the per-document limit. A question with several relevant documents
# cannot be answered by ten chunks of one of them, and that is what the
# uncapped configs do: for "what runs before MGSL006" they return ten chunks of
# MGSL006 and none of the six processes in its declared chain.
# || `cap` es el tope por documento. Una pregunta con varios documentos
# relevantes no se puede responder con diez chunks de uno solo, y es lo que
# hacen las configs sin tope: para "qué corre antes de MGSL006" devuelven diez
# chunks de MGSL006 y ninguno de los seis procesos de su cadena declarada.
CONFIGS: dict[str, tuple[tuple[str, ...], int | None]] = {
    "vector": (("vector",), None),
    "lexical": (("lexical",), None),
    "vector+exact": (DEFAULT_BRANCHES, None),
    "fused": (ALL_BRANCHES, None),
    "vector+exact cap1": (DEFAULT_BRANCHES, 1),
    "vector+exact cap2": (DEFAULT_BRANCHES, 2),
    "vector+exact cap3": (DEFAULT_BRANCHES, 3),
    "fused cap1": (ALL_BRANCHES, 1),
    "vector cap1": (("vector",), 1),
}


def load_golden() -> dict:
    if not GOLDEN_PATH.exists():
        print(
            f"{GOLDEN_PATH} not found. Run scripts/draft_golden_set.py first.", file=sys.stderr
        )
        raise SystemExit(1)
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def precision_at_k(document_ids: list[str], relevant: set[str], k: int) -> float:
    """``hits / k`` over the first k results, as the course computes it.

    Counted over DOCUMENTS and de-duplicated: several chunks of one relevant
    document are one hit, not five. Otherwise a config that floods the top-k
    with one document would score better for doing the thing this change is
    trying to avoid.

    || ``hits / k`` sobre los primeros k, como lo calcula el curso. Se cuenta por
    DOCUMENTO y sin duplicados: varios chunks de un documento relevante son un
    acierto, no cinco. Si no, una config que inunda el top-k con un solo
    documento puntuaría mejor justamente por hacer lo que este cambio evita.
    """
    seen: set[str] = set()
    hits = 0
    for document_id in document_ids[:k]:
        if document_id in relevant and document_id not in seen:
            hits += 1
        seen.add(document_id)
    return hits / k


def rank_of_first_hit(document_ids: list[str], relevant: set[str]) -> int | None:
    """The position of the first relevant document, 1-based, or ``None``.

    For a question with ONE relevant document, ``precision@10`` caps at 0.10 and
    says almost nothing. What matters there is whether the document came back at
    all and how high: a user reading the first three results either finds their
    answer or does not.

    || La posicion del primer documento relevante, desde 1, o ``None``. Para una
    pregunta con UN solo relevante, ``precision@10`` tiene techo 0,10 y no dice
    casi nada. Lo que importa ahi es si el documento volvio y que tan arriba: un
    usuario que lee los primeros tres resultados encuentra su respuesta o no.
    """
    for position, document_id in enumerate(document_ids, start=1):
        if document_id in relevant:
            return position
    return None


def ceiling_at_k(relevant: set[str], k: int) -> float:
    """The best precision@k this question allows.

    || La mejor precision@k que esta pregunta permite.
    """
    return min(len(relevant), k) / k


async def evaluate(name, branches, cap, questions, filters, retriever, *, k: int) -> dict:
    precisions: list[float] = []
    ceilings: list[float] = []
    latencies: list[float] = []
    ranks: list[int | None] = []
    per_question: dict[str, dict] = {}

    for question in questions:
        relevant = set(question["relevant_document_ids"])
        distractors = set(question["distractor_document_ids"])

        started = time.perf_counter()
        result = await retriever.retrieve(
            question["question"], filters, limit=k, branches=branches, max_per_document=cap
        )
        latencies.append((time.perf_counter() - started) * 1000)

        found = [chunk.document_id for chunk in result.chunks]
        precision = precision_at_k(found, relevant, k)
        ceiling = ceiling_at_k(relevant, k)
        precisions.append(precision)
        ceilings.append(ceiling)
        rank = rank_of_first_hit(found, relevant)
        ranks.append(rank)
        per_question[question["id"]] = {
            "precision": precision,
            "ceiling": ceiling,
            "rank_of_first_hit": rank,
            # How many of the deliberate distractors it fell for. A config that
            # scores the same but takes fewer distractors is the better one.
            # || Cuántos distractores deliberados se comió. Una config que
            # puntúa igual pero se come menos distractores es la mejor.
            "distractors_hit": len({d for d in found[:k] if d in distractors}),
        }

    found_at_all = [r for r in ranks if r is not None]
    return {
        "config": name,
        "cap": cap,
        "precision": statistics.fmean(precisions),
        "ceiling": statistics.fmean(ceilings),
        "latency_ms": statistics.fmean(latencies),
        # Did anything relevant come back at all, and how high. For a question
        # with one relevant document this is the number that means something.
        # || Si volvio algo relevante y que tan arriba. Para una pregunta con un
        # solo relevante, este es el numero que dice algo.
        "found_rate": len(found_at_all) / len(ranks) if ranks else 0.0,
        "top3_rate": sum(1 for r in found_at_all if r <= 3) / len(ranks) if ranks else 0.0,
        "mean_rank": statistics.fmean(found_at_all) if found_at_all else None,
        "distractors_hit": sum(v["distractors_hit"] for v in per_question.values()),
        "per_question": per_question,
    }


async def run(args) -> int:
    golden = load_golden()
    questions = golden["questions"]
    pending = golden.get("status") == "PENDING_REVIEW"
    unreviewed = sum(
        1 for q in questions if q.get("review", {}).get("annotation_is_correct") is None
    )

    settings = get_settings()
    filters = SearchFilters(settings.TENANT_ID, settings.DOC_VERSION)
    wanted = args.config or list(CONFIGS)

    if pending:
        print("!! GOLDEN SET PENDIENTE DE REVISIÓN")
        print(f"!! {unreviewed} de {len(questions)} preguntas sin revisar.")
        print("!! Los números de abajo NO son la calidad del sistema todavía.\n")

    async with get_async_session_factory()() as session:
        from app.dependencies import get_embedder

        retriever = HybridRetriever(ChunkRepository(session), get_embedder())
        results = []
        for name in wanted:
            branches, cap = CONFIGS[name]
            result = await evaluate(
                name, branches, cap, questions, filters, retriever, k=args.k
            )
            results.append(result)
            print(
                f"  {name:<18} p@{args.k} {result['precision']:.3f}"
                f"/{result['ceiling']:.3f}"
                f"  encontro {result['found_rate']:>4.0%}"
                f"  en top3 {result['top3_rate']:>4.0%}"
                f"  distr {result['distractors_hit']:>3}"
                f"  {result['latency_ms']:6.0f} ms"
            )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        render_report(results, golden, args.k, pending, unreviewed), encoding="utf-8"
    )
    print(f"\nWrote {REPORT_PATH}")
    return 0


def render_report(results, golden, k, pending, unreviewed) -> str:
    questions = golden["questions"]
    lines = [
        "# Evaluación de recuperación — precision@k sobre el golden set",
        "",
        "> Si la terminología de acá abajo no te dice nada, empezá por",
        "> [COMO_LEER.md](COMO_LEER.md): explica cada término sobre una pregunta real.",
        "",
    ]

    if pending:
        lines += [
            "> **El golden set está PENDIENTE DE REVISIÓN.**",
            f"> {unreviewed} de {len(questions)} preguntas no fueron revisadas por nadie que",
            "> conozca el negocio. Un golden set borradoreado por el mismo sistema que se",
            "> evalúa contra él no mide la calidad del sistema: mide si el sistema coincide",
            "> consigo mismo. Los números de acá abajo sirven para **comparar",
            "> configuraciones entre sí**, no para afirmar que la recuperación es buena.",
            "",
        ]

    lines += [
        "## Cómo leer estos números",
        "",
        f"`precision@{k} = aciertos / {k}`, contado por documento y sin duplicados: varios",
        "chunks de un documento relevante son un acierto, no cinco. Si no, una",
        "configuración que inunda el top-k con un solo documento puntuaría mejor por hacer",
        "justamente lo que hay que evitar.",
        "",
        f"El **techo** es el mejor `precision@{k}` que el conjunto permite: una pregunta con",
        f"3 relevantes y k={k} no puede pasar de {3/k:.2f}. Un puntaje de 0,28 sobre un techo",
        "de 0,30 y uno de 0,28 sobre un techo de 1,00 son resultados muy distintos, y el",
        "número solo no los distingue.",
        "",
        "**Distractores** cuenta cuántos documentos deliberadamente parecidos-pero-irrelevantes",
        "entraron al top-k. Dos configuraciones con el mismo puntaje no son iguales si una",
        "se come más distractores.",
        "",
        "## Resultados",
        "",
        f"| Config | precision@{k} | techo | % del techo | distractores | ms/consulta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        share = result["precision"] / result["ceiling"] if result["ceiling"] else 0.0
        lines.append(
            f"| `{result['config']}` | {result['precision']:.3f} | {result['ceiling']:.3f} "
            f"| {share:.0%} | {result['distractors_hit']} | {result['latency_ms']:.1f} |"
        )

    by_type: dict[str, list[str]] = {}
    for question in questions:
        by_type.setdefault(question["type"], []).append(question["id"])

    lines += ["", "## Por tipo de pregunta", "", "| Tipo | preguntas | " + " | ".join(
        f"`{r['config']}`" for r in results
    ) + " |", "|---|---:|" + "---:|" * len(results)]
    for kind, ids in sorted(by_type.items()):
        cells = []
        for result in results:
            values = [result["per_question"][qid]["precision"] for qid in ids]
            cells.append(f"{statistics.fmean(values):.3f}")
        lines.append(f"| `{kind}` | {len(ids)} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "### Qué significa cada tipo",
        "",
    ]
    for kind, meaning in golden.get("what_the_types_mean", {}).items():
        lines.append(f"- **`{kind}`**: {meaning}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=10, help="Results per query.")
    parser.add_argument(
        "--config", action="append", choices=list(CONFIGS), default=None,
        help="Which configurations to evaluate (default: all).",
    )
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())

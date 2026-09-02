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
#
# The third element is whether to decompose compound questions. It is a
# separate config and not a new default because the change is deliberately
# additive: `precision@k` does not move, and the value shows up in the recall of
# the candidate set instead. Ver `openspec/changes/add-query-decomposition`.
# || El tercer elemento es si descomponer las preguntas compuestas. Es una
# config aparte y no un default nuevo porque el cambio es a propósito aditivo:
# `precision@k` no se mueve, y el valor aparece en el recall del candidato.
CONFIGS: dict[str, tuple[tuple[str, ...], int | None, bool]] = {
    "vector": (("vector",), None, False),
    "lexical": (("lexical",), None, False),
    "vector+exact": (DEFAULT_BRANCHES, None, False),
    "fused": (ALL_BRANCHES, None, False),
    "vector+exact cap1": (DEFAULT_BRANCHES, 1, False),
    "vector+exact cap2": (DEFAULT_BRANCHES, 2, False),
    "vector+exact cap3": (DEFAULT_BRANCHES, 3, False),
    "fused cap1": (ALL_BRANCHES, 1, False),
    "vector cap1": (("vector",), 1, False),
    "vector+exact cap1 +split": (DEFAULT_BRANCHES, 1, True),
    "fused cap1 +split": (ALL_BRANCHES, 1, True),
}

# How wide the candidate set is when measuring recall. A relevant document
# inside it is a RANK problem, which a reranker can fix; outside it is a RECALL
# problem, which no reordering can. Keeping the two apart is the whole reason
# this number exists.
# || Qué tan ancho es el candidato al medir recall. Un documento relevante
# adentro es un problema de RANGO, que un reranker arregla; afuera es un
# problema de RECALL, que ningún reordenamiento arregla. Separar los dos es toda
# la razón por la que este número existe.
CANDIDATE_WIDTH = 60


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


async def evaluate(
    name, branches, cap, questions, filters, retriever, *, k: int, split: bool = False
) -> dict:
    precisions: list[float] = []
    ceilings: list[float] = []
    latencies: list[float] = []
    ranks: list[int | None] = []
    per_question: dict[str, dict] = {}
    # Pair-level buckets. A question with three relevant documents is three
    # measurements, not one, and averaging per question hides which of the three
    # failed and why.
    # || Cubetas a nivel de par. Una pregunta con tres documentos relevantes son
    # tres mediciones y no una, y promediar por pregunta esconde cuál de las tres
    # falló y por qué.
    in_top_k = rank_problem = recall_problem = 0

    for question in questions:
        relevant = set(question["relevant_document_ids"])
        distractors = set(question["distractor_document_ids"])

        # ONE retrieval, sliced twice. `cap_per_group` is a streaming filter
        # over an ordered list, so the first k of a 60-wide answer are exactly
        # the answer at limit=k -- the same invariant the decomposition change
        # relies on, and `test_appending_never_changes_the_capped_prefix` pins
        # it. Two calls per question doubled the eval's runtime for nothing.
        # || UNA búsqueda, rebanada dos veces. `cap_per_group` es un filtro en
        # streaming sobre una lista ordenada, así que los primeros k de una
        # respuesta de 60 son exactamente la respuesta con limit=k — la misma
        # invariante en la que se apoya la descomposición. Dos llamadas por
        # pregunta duplicaban el tiempo del eval al vacío.
        started = time.perf_counter()
        wide = await retriever.retrieve(
            question["question"],
            filters,
            limit=CANDIDATE_WIDTH,
            branches=branches,
            max_per_document=cap,
            decompose_query=split,
        )
        # The latency of a CANDIDATE_WIDTH retrieval, which overstates a k=10
        # query by the cost of rehydrating 60 rows instead of 10. The branches
        # cost the same either way: they always return `branch_limit`.
        # || La latencia de una búsqueda de CANDIDATE_WIDTH, que sobreestima una
        # consulta k=10 por lo que cuesta rehidratar 60 filas en lugar de 10.
        # Las ramas cuestan lo mismo: siempre devuelven `branch_limit`.
        latencies.append((time.perf_counter() - started) * 1000)

        wide_documents = [chunk.document_id for chunk in wide.chunks]
        found = wide_documents[:k]
        for document_id in question["relevant_document_ids"]:
            if document_id in found[:k]:
                in_top_k += 1
            elif document_id in wide_documents:
                rank_problem += 1
            else:
                recall_problem += 1
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
        # Pair-level, and the metrics that actually separate the two failures.
        # `pairs_rank` is what a reranker can convert; `pairs_recall` is what it
        # structurally cannot, because reordering does not bring back what never
        # came. They are disjoint sets and need different fixes.
        # || A nivel de par, y las métricas que de verdad separan las dos
        # fallas. `pairs_rank` es lo que un reranker puede convertir;
        # `pairs_recall` es lo que estructuralmente no puede, porque reordenar
        # no trae lo que no vino. Son conjuntos disjuntos y piden arreglos
        # distintos.
        "pairs_top_k": in_top_k,
        "pairs_rank": rank_problem,
        "pairs_recall": recall_problem,
        "pairs_total": in_top_k + rank_problem + recall_problem,
        "per_question": per_question,
    }


async def run(args) -> int:
    golden = load_golden()
    questions = golden["questions"]
    if args.human_only:
        questions = [q for q in questions if q.get("type") == "user_question"]
        # The report renderer walks `golden["questions"]` to group per question,
        # so it has to see the same subset or it looks up ids that were never
        # evaluated.
        # || El renderizador del reporte recorre `golden["questions"]` para
        # agrupar por pregunta, así que tiene que ver el mismo subconjunto o
        # busca ids que nunca se evaluaron.
        golden = {**golden, "questions": questions}
        print(f"Solo las {len(questions)} preguntas escritas y revisadas por una persona.\n")
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
            branches, cap, split = CONFIGS[name]
            result = await evaluate(
                name, branches, cap, questions, filters, retriever, k=args.k, split=split
            )
            results.append(result)
            recall = (result["pairs_total"] - result["pairs_recall"]) / result["pairs_total"]
            print(
                f"  {name:<26} p@{args.k} {result['precision']:.3f}"
                f"/{result['ceiling']:.3f}"
                f"  encontro {result['found_rate']:>4.0%}"
                f"  recall@{CANDIDATE_WIDTH} {recall:>4.0%}"
                f"  rango {result['pairs_rank']:>3}"
                f"  perdidos {result['pairs_recall']:>3}"
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
    parser.add_argument(
        "--human-only", action="store_true",
        help=(
            "Only the questions a person wrote and reviewed. The drafted ones "
            "are unreviewed, so mixing them in makes every number provisional."
        ),
    )
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())

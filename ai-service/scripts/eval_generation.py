"""Fidelity of generated answers against the golden set.

For every question that has a known expected ``document_id``, the
``citations`` attached to the generated answer MUST include at least one of
them. Those citations are the retrieved ``SearchHit``s — not the markers the
model wrote — so this is the check the approval criterion asks for: a
citation you can verify against what was actually retrieved.

When the LLM runs, the script also reports ``grounded_rate`` (the output
guardrail) and ``inline_hit`` (the prose itself named an expected document).
``--skip-llm`` measures citation coverage alone, without paying for a
completion: the citations of ``POST /answer`` are the hits, so coverage does
not depend on the model.

Usage:
    docker compose up -d   # or a reachable DATABASE_URL
    uv run python scripts/eval_generation.py --source curated
    uv run python scripts/eval_generation.py --source curated --limit 8
    uv run python scripts/eval_generation.py --source both --skip-llm

|| Fidelidad de las respuestas generadas contra el golden set. Para cada
pregunta con un ``document_id`` esperado conocido, las ``citations`` de la
respuesta generada TIENEN que incluir al menos uno. Esas citas son los
``SearchHit`` recuperados —no los marcadores que escribió el modelo— así que
este es el chequeo que pide el criterio de aprobación: una cita verificable
contra lo que realmente se recuperó.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.foundation.persistence.database import get_async_session_factory
from app.generation.rag.answer import generate_answer
from app.generation.rag.guardrails import citations_cover_expected, extract_cited_document_ids
from app.generation.rag.retrieval.hybrid import DEFAULT_BRANCHES, HybridRetriever
from app.generation.rag.store.repository import ChunkRepository, SearchFilters

CURATED_PATH = Path("evals/golden_curated.json")
RETRIEVAL_PATH = Path("evals/golden_retrieval.json")
REPORT_PATH = Path("evals/GENERATION_EVAL.md")


def load_questions(source: str) -> list[dict]:
    """Load golden questions that carry at least one expected document_id.

    || Carga preguntas del golden que traen al menos un document_id esperado.
    """
    paths: list[Path] = []
    if source in {"curated", "both"}:
        paths.append(CURATED_PATH)
    if source in {"retrieval", "both"}:
        paths.append(RETRIEVAL_PATH)

    questions: list[dict] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            print(f"{path} not found.", file=sys.stderr)
            raise SystemExit(1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        for question in payload.get("questions", []):
            qid = question["id"]
            if qid in seen:
                continue
            expected = question.get("relevant_document_ids") or []
            if not expected:
                continue
            seen.add(qid)
            questions.append(question)
    return questions


async def evaluate(
    questions: list[dict],
    *,
    skip_llm: bool,
    limit: int,
    max_per_document: int,
) -> dict:
    settings = get_settings()
    filters = SearchFilters(settings.TENANT_ID, settings.DOC_VERSION)
    rows: list[dict] = []

    async with get_async_session_factory()() as session:
        from app.dependencies import get_answer_llm, get_embedder, get_reranker

        retriever = HybridRetriever(ChunkRepository(session), get_embedder())
        llm = None if skip_llm else get_answer_llm()
        reranker = get_reranker()

        for question in questions:
            expected = set(question["relevant_document_ids"])
            started = time.perf_counter()

            if skip_llm:
                result = await retriever.retrieve(
                    question["question"],
                    filters,
                    limit=limit,
                    max_per_document=max_per_document,
                    branches=DEFAULT_BRANCHES,
                    decompose_query=True,
                    reranker=reranker,
                )
                citation_ids = [chunk.document_id for chunk in result.chunks]
                inline_ids: list[str] = []
                grounded = True
                answer_text = ""
            else:
                response = await generate_answer(
                    question["question"],
                    filters=filters,
                    retriever=retriever,
                    llm=llm,
                    limit=limit,
                    max_per_document=max_per_document,
                    branches=DEFAULT_BRANCHES,
                    decompose_query=True,
                    reranker=reranker,
                )
                citation_ids = [hit.document_id for hit in response.citations]
                inline_ids = extract_cited_document_ids(response.answer)
                grounded = response.grounded
                answer_text = response.answer

            elapsed_ms = (time.perf_counter() - started) * 1000
            covered = citations_cover_expected(citation_ids, expected)
            inline_hit = citations_cover_expected(inline_ids, expected) if inline_ids else False
            rows.append(
                {
                    "id": question["id"],
                    "type": question.get("type", ""),
                    "expected": sorted(expected),
                    "citations": citation_ids,
                    "covered": covered,
                    "grounded": grounded,
                    "inline_ids": inline_ids,
                    "inline_hit": inline_hit,
                    "latency_ms": elapsed_ms,
                    "answer_chars": len(answer_text),
                }
            )
            flag = "ok" if covered else "MISS"
            print(
                f"  {flag:<4} {question['id']:<40} "
                f"covered={covered} grounded={grounded} "
                f"{elapsed_ms:7.0f} ms"
            )

    n = len(rows) or 1
    return {
        "skip_llm": skip_llm,
        "questions": len(rows),
        "citation_coverage": sum(1 for row in rows if row["covered"]) / n,
        "grounded_rate": sum(1 for row in rows if row["grounded"]) / n,
        "inline_hit_rate": sum(1 for row in rows if row["inline_hit"]) / n,
        "latency_ms": sum(row["latency_ms"] for row in rows) / n,
        "rows": rows,
        "branches": DEFAULT_BRANCHES,
    }


def render_report(result: dict, source: str) -> str:
    """Keep GENERATION_EVAL.md's method section; replace the results block.

    || Conserva la sección de método de GENERATION_EVAL.md; reemplaza el bloque
    de resultados.
    """
    method_path = REPORT_PATH
    existing = method_path.read_text(encoding="utf-8") if method_path.exists() else ""
    marker = "## Resultados"
    head = existing.split(marker, 1)[0].rstrip()
    if not head:
        head = "# Evaluación de generación — fidelidad de citas\n"

    lines = [
        head,
        "",
        marker,
        "",
        (
            f"Corrida: `source={source}`, `skip_llm={result['skip_llm']}`, "
            f"{result['questions']} preguntas, pipeline "
            f"`{'+'.join(result['branches'])}` cap=1 +split +rerank."
        ),
        "",
        "| métrica | valor | qué mide |",
        "|---|---:|---|",
        (
            f"| `citation_coverage` | {result['citation_coverage']:.0%} | "
            "fracción de preguntas cuyo `document_id` esperado aparece en `citations` |"
        ),
        (
            f"| `grounded_rate` | {result['grounded_rate']:.0%} | "
            "fracción de respuestas sin `document_id` inventado en la prosa |"
        ),
        (
            f"| `inline_hit` | {result['inline_hit_rate']:.0%} | "
            "fracción cuya prosa nombra un documento esperado |"
        ),
        f"| ms/pregunta | {result['latency_ms']:.0f} | latencia media retrieve+generate |",
        "",
        "## Por pregunta",
        "",
        "| id | cubrió | grounded | esperado | citations |",
        "|---|---|---|---|---|",
    ]
    for row in result["rows"]:
        covered = "sí" if row["covered"] else "NO"
        grounded = "sí" if row["grounded"] else "NO"
        lines.append(
            f"| `{row['id']}` | {covered} | {grounded} | "
            f"{', '.join(row['expected'])} | {', '.join(row['citations']) or '—'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=("curated", "retrieval", "both"),
        default="curated",
        help="Which golden file(s) to score. curated is human-authored.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Chunks per answer.")
    parser.add_argument("--max-per-document", type=int, default=1)
    parser.add_argument(
        "--max-questions",
        type=int,
        default=None,
        help="Score only the first N questions (smoke).",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Measure citation coverage from retrieval only, no completion.",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Rewrite the Resultados section of evals/GENERATION_EVAL.md.",
    )
    args = parser.parse_args()

    questions = load_questions(args.source)
    if args.max_questions is not None:
        questions = questions[: args.max_questions]
    print(f"Scoring {len(questions)} questions from {args.source} (skip_llm={args.skip_llm})")

    result = asyncio.run(
        evaluate(
            questions,
            skip_llm=args.skip_llm,
            limit=args.limit,
            max_per_document=args.max_per_document,
        )
    )
    print(
        f"\ncitation_coverage {result['citation_coverage']:.0%}  "
        f"grounded_rate {result['grounded_rate']:.0%}  "
        f"inline_hit {result['inline_hit_rate']:.0%}  "
        f"{result['latency_ms']:.0f} ms/q"
    )
    if args.write_report:
        REPORT_PATH.write_text(render_report(result, args.source), encoding="utf-8")
        print(f"Wrote {REPORT_PATH}")
    return 0 if result["citation_coverage"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

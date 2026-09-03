"""Fast proxy for comparing two versions of the retrieval, over free labels.

1871 documents have a UNIQUE title, which gives a labelled set with nothing to
annotate: the title as the query, that document as the answer. Since there is
exactly one correct document per query, the metric is a hit rate in the top k.

THIS IS A PROXY AND IT IS NOT THE QUALITY OF THE SYSTEM. A title is not a
question, so the metric rewards resembling a title -- a change that helps titles
and not questions would look like an improvement. Its ceiling is not 100% either.
What it is good for is running in seconds while the fusion is being tuned.

What gets reported is precision@k over the hand-annotated golden set, which is
what the course does (`scripts/eval_retrieval_s10.py`).

Usage:
    uv run python scripts/eval_retrieval_proxy.py --limit 60
    uv run python scripts/eval_retrieval_proxy.py --full --config fused

|| Proxy rápido para comparar dos versiones de la recuperación, con etiquetas
gratis. 1871 documentos tienen título ÚNICO, lo que da un conjunto etiquetado sin
anotar nada. Como hay exactamente un documento correcto por consulta, la métrica
es una tasa de acierto en los primeros k.

ESTO ES UN PROXY Y NO ES LA CALIDAD DEL SISTEMA. Un título no es una pregunta,
así que la métrica premia parecerse a un título. Para lo que sirve es para correr
en segundos mientras se ajusta la fusión.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
import time
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.config import get_settings
from app.foundation.persistence.database import get_async_session_factory
from app.generation.rag.store.repository import ChunkRepository, SearchFilters

REPORT_PATH = Path("data/retrieval_proxy_report.md")

# Only documents whose title is unique: 349 share theirs with another, and there
# the query is ambiguous by construction -- `VIC014_k` "fails" by returning
# `SGC001_k`, whose title is IDENTICAL.
# || Solo documentos con título único: 349 lo comparten con otro, y ahí la
# consulta es ambigua por construcción.
_ELIGIBLE_SQL = """
WITH titled AS (
    SELECT DISTINCT document_id, document_title AS title
    FROM chunks
    WHERE tenant_id = :tenant AND doc_version = :version
      AND document_title IS NOT NULL
      AND length(document_title) > 12
      AND document_title NOT LIKE '%|%'
), unique_titles AS (
    SELECT title FROM titled GROUP BY title HAVING count(*) = 1
)
SELECT t.document_id, t.title
FROM titled t JOIN unique_titles u ON u.title = t.title
ORDER BY t.document_id
"""

CONFIGS = ("vector", "lexical", "vector_exact", "fused")


async def evaluate(config: str, sample, filters, embedder, session, *, ks) -> dict:
    from app.generation.rag.retrieval.hybrid import HybridRetriever

    repository = ChunkRepository(session)
    retriever = HybridRetriever(repository, embedder)
    biggest = max(ks)

    hits = {k: 0 for k in ks}
    latencies: list[float] = []
    misses: list[tuple[str, str, list[str]]] = []

    # Embedded in one batch: one call per query would make the run pointlessly
    # slow and expensive for a metric meant to be cheap.
    # || Embebidos en un lote: una llamada por consulta haría la corrida
    # lenta y cara sin sentido para una métrica que quiere ser barata.
    vectors = embedder.embed([title for _, title in sample]) if config != "lexical" else None

    for index, (document_id, title) in enumerate(sample):
        started = time.perf_counter()
        if config == "vector":
            found = [h.document_id for h in await repository.search(
                vectors[index], filters, limit=biggest)]
        elif config == "lexical":
            found = [h.document_id for h in await repository.search_lexical(
                title, filters, limit=biggest)]
        elif config == "vector_exact":
            result = await retriever.retrieve(
                title, filters, limit=biggest, branches=("vector", "exact")
            )
            found = [c.document_id for c in result.chunks]
        else:
            from app.generation.rag.retrieval.hybrid import ALL_BRANCHES

            result = await retriever.retrieve(
                title, filters, limit=biggest, branches=ALL_BRANCHES
            )
            found = [c.document_id for c in result.chunks]
        latencies.append((time.perf_counter() - started) * 1000)

        for k in ks:
            if document_id in found[:k]:
                hits[k] += 1
        if document_id not in found:
            misses.append((document_id, title, found[:3]))

    total = len(sample)
    return {
        "config": config,
        "hit_rate": {k: hits[k] / total for k in ks},
        "latency_ms": statistics.fmean(latencies),
        "misses": misses,
        "total": total,
    }


async def run(args) -> int:
    settings = get_settings()
    filters = SearchFilters(settings.TENANT_ID, settings.DOC_VERSION)
    ks = (1, 5, 10)

    async with get_async_session_factory()() as session:
        rows = list(
            await session.execute(
                text(_ELIGIBLE_SQL),
                {"tenant": filters.tenant_id, "version": filters.doc_version},
            )
        )
        if not rows:
            print("No eligible documents. Is the corpus loaded?", file=sys.stderr)
            return 1

        eligible = [(row.document_id, row.title) for row in rows]
        sample = eligible
        if not args.full:
            random.seed(args.seed)
            sample = random.sample(eligible, min(args.limit, len(eligible)))

        print(f"Documents with a unique title: {len(eligible):,}")
        print(f"Sample:                        {len(sample):,}  (seed {args.seed})")
        print()

        from app.dependencies import get_embedder

        embedder = get_embedder()
        results = []
        for config in args.config or CONFIGS:
            result = await evaluate(config, sample, filters, embedder, session, ks=ks)
            results.append(result)
            rates = "  ".join(f"@{k} {result['hit_rate'][k]:.0%}" for k in ks)
            print(f"  {config:<10} {rates}   {result['latency_ms']:6.1f} ms/consulta")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(results, len(eligible), ks), encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}")
    return 0


def render_report(results, eligible: int, ks) -> str:
    lines = [
        "# Proxy de recuperación — tasa de acierto sobre títulos únicos",
        "",
        "## Qué mide, y qué NO",
        "",
        "Usa el título de cada documento como consulta y espera ese documento como",
        f"respuesta. {eligible:,} documentos tienen título único, lo que da un conjunto",
        "etiquetado sin anotar nada.",
        "",
        "**NO es la calidad del sistema.** Un título no es una pregunta: nadie escribe",
        '*"Rechazo de cobros automáticos"*, escribe *"por qué se rechazó este cobro"*.',
        "La métrica premia **parecerse al título**, así que un cambio que ayude a los",
        "títulos y no a las preguntas se vería como una mejora.",
        "",
        "Otros dos límites:",
        "",
        "- El techo no es 100%. 349 documentos comparten título con otro y quedan",
        "  afuera; entre los que quedan sigue habiendo títulos casi idénticos.",
        "- Un fallo contado puede ser correcto: `VIC014_k` devolvió `SGC001_k`, y los",
        "  dos documentos tienen el título **idéntico**.",
        "",
        "Sirve para **comparar dos versiones del mismo sistema** mientras se lo",
        "construye. Lo que se reporta como calidad es `precision@k` sobre el golden set",
        "anotado a mano, como hace el curso.",
        "",
        "## Resultados",
        "",
        "| Config | " + " | ".join(f"acierto@{k}" for k in ks) + " | ms/consulta |",
        "|---|" + "---:|" * (len(ks) + 1),
    ]
    for result in results:
        rates = " | ".join(f"{result['hit_rate'][k]:.0%}" for k in ks)
        lines.append(f"| `{result['config']}` | {rates} | {result['latency_ms']:.1f} |")

    for result in results:
        if not result["misses"]:
            continue
        lines += ["", f"### Fallos de `{result['config']}` ({len(result['misses'])})", ""]
        for document_id, title, found in result["misses"][:10]:
            lines.append(f"- **{document_id}** *{title[:60]}* → trajo `{'`, `'.join(found)}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=60, help="Sample size.")
    parser.add_argument("--full", action="store_true", help="Every eligible document.")
    parser.add_argument("--seed", type=int, default=7, help="So the sample is reproducible.")
    parser.add_argument(
        "--config", action="append", choices=CONFIGS, default=None,
        help="Which configurations to evaluate (default: all).",
    )
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())

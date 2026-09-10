"""Both directions of the referential resolver, on a multi-turn golden set.

The resolver of ``conversation-memory`` was measured in one direction only:
its ``design.md`` records that it does not rewrite a question that names its
own subject (the false positive), and says outright that the other direction
is unknown. That asymmetry flatters it. A resolver that never rewrites scores
a perfect zero on false positives, so the number alone cannot tell a
conservative resolver from a broken one. This script reports the pair.

Two modes, and the default is the cheap one:

* **resolver** (default) — walks each sequence turn by turn and calls
  ``resolve()`` directly. The facts handed to turn N are built from the
  ANNOTATED documents of turn N-1, not from what retrieval actually
  returned. That is the isolation that makes the number mean something: a
  false negative here is the resolver failing on a perfect previous turn, not
  retrieval having missed the referent first. No database, no LLM, no server.
* **--through-graph** — drives the same sequences through the real endpoints
  (``POST /answer/session`` → ``POST /answer/agentic/start`` → poll
  ``GET /answer/agentic/{id}/progress``) so what gets measured is what a user
  receives: the resolution the planner actually applied, the anchors in
  force, whether memory displaced evidence (``dropped_hits``) and which
  documents were cited. Needs a reachable Postgres and spends completions.

The two are not redundant. The resolver mode measures ONE component under
ideal inputs; the graph mode measures the whole path and cannot separate a
resolver miss from a retrieval miss. Reporting only the second would hide
which piece to fix.

Usage:
    uv run python scripts/eval_multiturn.py
    uv run python scripts/eval_multiturn.py --write-report
    uv run python scripts/eval_multiturn.py --through-graph --write-report

|| Las dos direcciones del resolver referencial, sobre un golden set
multi-turno. El resolver estaba medido en una sola dirección y su propio
`design.md` lo dice. Esa asimetría lo favorece: un resolver que no reescribe
nunca saca cero en falsos positivos, así que el número solo no distingue un
resolver conservador de uno roto.

Dos modos. El default (`resolver`) camina las secuencias y llama a `resolve()`
con hechos armados desde los documentos ANOTADOS del turno anterior — esa es
la aislación que hace que el número signifique algo: un falso negativo acá es
el resolver fallando sobre un turno anterior perfecto, no la recuperación
habiendo perdido el referente antes. `--through-graph` corre las mismas
secuencias por los endpoints reales, así lo que se mide es lo que recibe un
usuario.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.generation.conversation.models import ConversationFacts
from app.generation.conversation.resolver import resolve

GOLDEN_PATH = Path("evals/golden_multiturn.json")
REPORT_PATH = Path("evals/MULTITURN_EVAL.md")

# The three annotations a follow-up turn can carry. `clear` and `absent` are
# the two that score; `ambiguous` is recorded and never counted, because
# scoring it would mean picking one reading and then grading the resolver
# against our own pick.
# || Las tres anotaciones que puede llevar un turno posterior. `clear` y
# `absent` puntúan; `ambiguous` se registra y no se cuenta nunca.
CLEAR = "clear"
ABSENT = "absent"
AMBIGUOUS = "ambiguous"

# Verdicts. Four of them are failures and they are NOT interchangeable:
# `false_negative` is the resolver staying silent, `wrong_referent` is it
# speaking up and pointing somewhere else. The second is worse — it produces a
# confident search for a question nobody asked — so they never share a column.
# || Cuatro veredictos son fallas y no son intercambiables: `false_negative`
# es el resolver callándose; `wrong_referent` es hablando y apuntando a otro
# lado. El segundo es peor y por eso nunca comparten columna.
OK = "ok"
FALSE_NEGATIVE = "false_negative"
FALSE_POSITIVE = "false_positive"
PARTIAL_REFERENT = "partial_referent"
WRONG_REFERENT = "wrong_referent"
UNSCORED = "unscored"


@dataclass(frozen=True)
class TurnScore:
    """One follow-up turn, what the resolver did with it, and the verdict.

    || Un turno posterior, qué hizo el resolver con él, y el veredicto.
    """

    sequence_id: str
    n: int
    question: str
    referent: str
    rewritten: bool
    resolved_question: str
    substituted: list[str]
    expected_referents: list[str]
    verdict: str
    # Only the graph mode fills these; the resolver mode has no retrieval.
    # || Solo el modo grafo llena esto; el modo resolver no recupera nada.
    cited_document_ids: list[str] = field(default_factory=list)
    expected_document_ids: list[str] = field(default_factory=list)
    anchors_applied: list[str] = field(default_factory=list)
    dropped_hits: int | None = None
    status: str = ""

    @property
    def failed(self) -> bool:
        """|| Si este turno cuenta como falla."""
        return self.verdict in {FALSE_NEGATIVE, FALSE_POSITIVE, WRONG_REFERENT}


def score_turn(
    *,
    sequence_id: str,
    turn: dict,
    rewritten: bool,
    resolved_question: str,
    substituted: list[str],
) -> TurnScore:
    """Grade one follow-up turn against its human annotation.

    The quality of a rewrite is graded in three steps and not two, because
    "it rewrote" and "it rewrote correctly" are different claims and the
    change exists to stop reporting the first as if it were the second:

    * every named referent was expected → ``ok``
    * some expected, some invented → ``partial_referent``
    * none expected → ``wrong_referent``

    || Califica un turno posterior contra su anotación humana. La calidad de
    una reescritura se gradúa en tres pasos y no en dos, porque «reescribió»
    y «reescribió bien» son afirmaciones distintas y este change existe para
    dejar de reportar la primera como si fuera la segunda.
    """
    referent = turn["referent"]
    expected = list(turn.get("expected_referents") or [])
    common = {value.casefold() for value in expected}
    named = {value.casefold() for value in substituted}

    if referent == ABSENT:
        verdict = FALSE_POSITIVE if rewritten else OK
    elif referent == CLEAR:
        if not rewritten:
            verdict = FALSE_NEGATIVE
        elif not named & common:
            verdict = WRONG_REFERENT
        elif named <= common:
            verdict = OK
        else:
            verdict = PARTIAL_REFERENT
    else:
        verdict = UNSCORED

    return TurnScore(
        sequence_id=sequence_id,
        n=turn["n"],
        question=turn["question"],
        referent=referent,
        rewritten=rewritten,
        resolved_question=resolved_question,
        substituted=substituted,
        expected_referents=expected,
        expected_document_ids=list(turn.get("relevant_document_ids") or []),
        verdict=verdict,
    )


def summarize(scores: list[TurnScore]) -> dict:
    """The two directions, side by side, plus the quality of what it rewrote.

    Reported together on purpose. `false_negative_rate` alone rewards a
    resolver that fires on everything and `false_positive_rate` alone rewards
    one that never fires, so either number by itself re-opens the hole this
    measurement exists to close.

    || Las dos direcciones, juntas, más la calidad de lo que reescribió. Cada
    número solo premia el extremo opuesto, así que por separado vuelven a
    abrir el hueco que esta medición existe para cerrar.
    """
    clear = [s for s in scores if s.referent == CLEAR]
    absent = [s for s in scores if s.referent == ABSENT]
    ambiguous = [s for s in scores if s.referent == AMBIGUOUS]

    false_negatives = [s for s in clear if s.verdict == FALSE_NEGATIVE]
    false_positives = [s for s in absent if s.verdict == FALSE_POSITIVE]
    rewritten_clear = [s for s in clear if s.rewritten]

    return {
        "turns_scored": len(clear) + len(absent),
        "clear": len(clear),
        "absent": len(absent),
        "ambiguous": len(ambiguous),
        "false_negatives": len(false_negatives),
        "false_positives": len(false_positives),
        # Guarded against an empty bucket rather than assumed non-empty: a
        # golden set with no `absent` turns is a bad golden set, not a crash.
        # || Con guarda contra bucket vacío: un golden sin `absent` es un
        # golden malo, no un crash.
        "false_negative_rate": len(false_negatives) / len(clear) if clear else None,
        "false_positive_rate": len(false_positives) / len(absent) if absent else None,
        "quality_ok": sum(1 for s in rewritten_clear if s.verdict == OK),
        "quality_partial": sum(1 for s in rewritten_clear if s.verdict == PARTIAL_REFERENT),
        "quality_wrong": sum(1 for s in rewritten_clear if s.verdict == WRONG_REFERENT),
        "rewritten_clear": len(rewritten_clear),
        "ambiguous_rewritten": sum(1 for s in ambiguous if s.rewritten),
    }


def facts_for(previous_turn: dict | None) -> ConversationFacts | None:
    """The facts a perfect previous turn would have left behind.

    Built from the ANNOTATION and not from retrieval, which is what isolates
    the resolver. ``last_document_ids`` is what the resolver reaches for
    first, and the session replaces it every turn rather than accumulating —
    so this hands over the previous turn's documents only, never the whole
    sequence's.

    || Los hechos que habría dejado un turno anterior perfecto. Se arman
    desde la ANOTACIÓN y no desde la recuperación, que es lo que aísla al
    resolver. Se entregan los documentos del turno anterior y no los de toda
    la secuencia, porque la sesión reemplaza `last_document_ids` cada turno.
    """
    if previous_turn is None:
        return None
    documents = list(previous_turn.get("relevant_document_ids") or [])
    if not documents:
        return None
    return ConversationFacts(transaction_codes=documents, last_document_ids=documents)


def run_resolver_mode(sequences: list[dict]) -> list[TurnScore]:
    """Score every follow-up turn by calling the resolver directly.

    || Puntúa cada turno posterior llamando al resolver directo.
    """
    scores: list[TurnScore] = []
    for sequence in sequences:
        turns = sequence["turns"]
        for index, turn in enumerate(turns):
            if "referent" not in turn:
                continue
            resolved = resolve(turn["question"], facts_for(turns[index - 1]))
            scores.append(
                score_turn(
                    sequence_id=sequence["id"],
                    turn=turn,
                    rewritten=resolved.rewritten,
                    resolved_question=resolved.text,
                    substituted=list(resolved.substituted),
                )
            )
    return scores


def run_graph_mode(sequences: list[dict], *, poll_seconds: float, attempts: int) -> list[TurnScore]:
    """Drive the sequences through the real endpoints and score what came back.

    Uses FastAPI's ``TestClient`` against the real app rather than an HTTP
    call to a running server. It goes through the actual routers, request
    models and dependencies — including the service-token guard, which the
    client satisfies by reading the configured token — while needing no
    process to be up and no port to be free. What it does need is a reachable
    Postgres and a usable model credential, because the graph really runs.

    || Maneja las secuencias por los endpoints reales con el ``TestClient``
    de FastAPI en vez de una llamada HTTP a un servidor levantado: pasa por
    los routers, los modelos y las dependencias de verdad —incluido el guard
    del token, que el cliente satisface leyendo el token configurado— sin
    necesitar un proceso arriba ni un puerto libre. Sí necesita Postgres
    alcanzable y una credencial de modelo usable, porque el grafo corre.
    """
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    _use_selector_loop_on_windows()

    token = get_settings().SERVICE_TOKEN.strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    scores: list[TurnScore] = []

    with TestClient(app) as client:
        for sequence in sequences:
            created = client.post("/answer/session", headers=headers)
            created.raise_for_status()
            session_id = created.json()["session_id"]
            print(f"\n{sequence['id']}  session={session_id}")

            turns = sequence["turns"]
            for turn in turns:
                progress = _run_one_turn(
                    client,
                    headers=headers,
                    session_id=session_id,
                    question=turn["question"],
                    poll_seconds=poll_seconds,
                    attempts=attempts,
                )
                cited = [hit.get("document_id", "") for hit in progress.get("citations") or []]
                anchors = [
                    str(anchor.get("kind", ""))
                    for anchor in progress.get("anchors_applied") or []
                ]
                if "referent" not in turn:
                    print(
                        f"  turno {turn['n']}  {progress.get('status', '?'):<22} "
                        f"citó {', '.join(dict.fromkeys(cited)) or '—'}"
                    )
                    continue

                score = score_turn(
                    sequence_id=sequence["id"],
                    turn=turn,
                    rewritten=bool(progress.get("resolved_referents")),
                    resolved_question=progress.get("resolved_question") or turn["question"],
                    substituted=list(progress.get("resolved_referents") or []),
                )
                scores.append(
                    TurnScore(
                        **{
                            **score.__dict__,
                            "cited_document_ids": list(dict.fromkeys(cited)),
                            "anchors_applied": sorted(set(anchors)),
                            "dropped_hits": progress.get("dropped_hits"),
                            "status": str(progress.get("status") or ""),
                        }
                    )
                )
                print(
                    f"  turno {turn['n']}  {score.verdict:<16} "
                    f"reescribió={score.rewritten} "
                    f"citó {', '.join(dict.fromkeys(cited)) or '—'}"
                )
    return scores


def _use_selector_loop_on_windows() -> None:
    """Let psycopg's async pool run under ``TestClient`` on Windows.

    Windows defaults asyncio to ``ProactorEventLoop``, and psycopg refuses to
    run in async mode on it — so the LangGraph checkpointer's pool never
    finishes initializing, the graph comes up unavailable, and every
    ``/answer/agentic/start`` answers 503. Under uvicorn the loop is chosen by
    the server; here the loop is whatever this process has, so the choice is
    ours to make and this is the policy psycopg's own error message asks for.

    Scoped to this script on purpose. Nothing in ``app/`` sets a loop policy,
    and a script that runs a server in-process is not the place to start
    deciding that for the service.

    || Windows arranca asyncio con ``ProactorEventLoop`` y psycopg se niega a
    correr en async sobre ese loop: el pool del checkpointer de LangGraph no
    termina de inicializar, el grafo queda no disponible y cada
    ``/answer/agentic/start`` contesta 503. Bajo uvicorn el loop lo elige el
    servidor; acá el loop es el de este proceso, así que la decisión es
    nuestra, y esta es la política que pide el propio mensaje de psycopg.
    Limitado a este script a propósito: nada en ``app/`` fija una política de
    loop, y un script que corre el servidor in-process no es el lugar para
    empezar a decidirlo por el servicio.
    """
    if sys.platform != "win32":
        return
    policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy is not None:
        asyncio.set_event_loop_policy(policy())


def _run_one_turn(
    client,
    *,
    headers: dict,
    session_id: str,
    question: str,
    poll_seconds: float,
    attempts: int,
) -> dict:
    """One background run, polled until it stops running.

    A run that pauses at the human-review gate is NOT resumed. The gate
    firing is a legitimate outcome and approving it here would put this
    script's judgement into a number that is supposed to measure the
    system's.

    || Una corrida en background, sondeada hasta que deje de correr. Una que
    pausa en el gate NO se retoma: que el gate dispare es un resultado
    legítimo, y aprobarlo acá metería el criterio de este script en un número
    que mide el del sistema.
    """
    started = client.post(
        "/answer/agentic/start",
        json={"question": question, "session_id": session_id},
        headers=headers,
    )
    started.raise_for_status()
    thread_id = started.json()["thread_id"]

    for _ in range(attempts):
        progress = client.get(f"/answer/agentic/{thread_id}/progress", headers=headers)
        progress.raise_for_status()
        payload = progress.json()
        if payload.get("status") != "running":
            return payload
        time.sleep(poll_seconds)
    return {"status": "timeout", "thread_id": thread_id}


def render_report(
    summary: dict, scores: list[TurnScore], *, mode: str, golden: dict
) -> str:
    """Rewrite the results block, keeping whatever method section exists.

    Repeats the golden set's review state in the report itself, which is what
    `retrieval`'s spec requires of an unreviewed set: the file declaring it is
    not enough if the numbers travel without it.

    || Reescribe el bloque de resultados y conserva la sección de método.
    Repite el estado de revisión del golden en el reporte, que es lo que
    exige la spec de `retrieval`: que lo declare el archivo no alcanza si los
    números viajan sin eso.
    """
    marker = SECTION[mode]
    head, kept = _split_report(marker)
    if not head:
        head = "# Evaluación multi-turno — las dos direcciones del resolver\n"

    reviewed = _review_state(golden)
    fn = summary["false_negative_rate"]
    fp = summary["false_positive_rate"]
    lines = [
        head,
        "",
        marker,
        "",
        (
            f"Corrida: modo `{mode}`, {summary['turns_scored']} turnos puntuados "
            f"({summary['clear']} `clear`, {summary['absent']} `absent`) y "
            f"{summary['ambiguous']} `ambiguous` fuera de la métrica."
        ),
        "",
        reviewed,
        "",
        "| métrica | valor | qué mide |",
        "|---|---:|---|",
        (
            f"| `false_negative_rate` | {_pct(fn)} | de las preguntas con referente "
            "claro, cuántas quedaron sin resolver |"
        ),
        (
            f"| `false_positive_rate` | {_pct(fp)} | de las que se sostenían solas, "
            "cuántas fueron reescritas igual |"
        ),
        (
            f"| reescrituras correctas | {summary['quality_ok']}/{summary['rewritten_clear']}"
            " | de las que reescribió, cuántas nombraron solo el referente anotado |"
        ),
        (
            f"| reescrituras parciales | {summary['quality_partial']}"
            f"/{summary['rewritten_clear']} | nombró el referente correcto y además otro |"
        ),
        (
            f"| reescrituras erradas | {summary['quality_wrong']}/{summary['rewritten_clear']}"
            " | nombró un referente que no era |"
        ),
        (
            f"| `ambiguous` reescritas | {summary['ambiguous_rewritten']}"
            f"/{summary['ambiguous']} | informativo: no cuenta ni a favor ni en contra |"
        ),
        "",
        "### Por turno",
        "",
        "| secuencia | turno | pregunta | referente | reescribió | nombró | veredicto |",
        "|---|---:|---|---|---|---|---|",
    ]
    for score in scores:
        lines.append(
            f"| `{score.sequence_id}` | {score.n} | {score.question} | {score.referent} | "
            f"{'sí' if score.rewritten else 'no'} | "
            f"{', '.join(score.substituted) or '—'} | {score.verdict} |"
        )

    if mode == "through-graph":
        lines += [
            "",
            "### Lo que agregó el grafo",
            "",
            "| secuencia | turno | estado | citó | anchors | `dropped_hits` |",
            "|---|---:|---|---|---|---:|",
        ]
        for score in scores:
            lines.append(
                f"| `{score.sequence_id}` | {score.n} | {score.status or '—'} | "
                f"{', '.join(score.cited_document_ids) or '—'} | "
                f"{', '.join(score.anchors_applied) or '—'} | "
                f"{score.dropped_hits if score.dropped_hits is not None else '—'} |"
            )
    return "\n".join(lines) + "\n" + kept


SECTION = {
    "resolver": "## Resultados — modo resolver",
    "through-graph": "## Resultados — por el grafo",
}


def _split_report(marker: str) -> tuple[str, str]:
    """The method section, and the OTHER mode's results left untouched.

    The two modes write the same file and neither may erase the other. They
    measure different things — one component under ideal inputs, the whole
    path under real ones — and the difference between them is the finding: in
    the resolver mode a turn is handed one annotated document, while through
    the graph the previous turn cited ten, so the same rewrite that scores
    `ok` in isolation can name a second referent nobody asked about.

    Written this way because the neighbouring eval already paid for the
    alternative: `eval_retrieval.py` run with a single `--config` overwrote
    the whole four-configuration comparison table, and it had to be recovered
    from git.

    || Los dos modos escriben el mismo archivo y ninguno puede borrar al
    otro. La diferencia entre ellos ES el hallazgo: en modo resolver el turno
    recibe un documento anotado, y por el grafo el turno anterior citó diez,
    así que la misma reescritura que puntúa `ok` aislada puede nombrar un
    segundo referente que nadie pidió. Se escribe así porque el eval vecino ya
    pagó la alternativa: `eval_retrieval.py` con un solo `--config` sobrescribió
    la tabla completa de cuatro configuraciones y hubo que recuperarla de git.
    """
    if not REPORT_PATH.exists():
        return "", ""
    existing = REPORT_PATH.read_text(encoding="utf-8")

    # The head is whatever precedes the FIRST results section of either mode,
    # so the hand-written method section survives every run.
    # || El encabezado es lo que precede a la PRIMERA sección de resultados de
    # cualquiera de los modos, así la sección de método sobrevive cada corrida.
    starts = [existing.find(title) for title in SECTION.values()]
    starts = [start for start in starts if start >= 0]
    head = existing[: min(starts)].rstrip() if starts else existing.rstrip()

    other = next(title for title in SECTION.values() if title != marker)
    index = existing.find(other)
    if index < 0:
        return head, ""
    end = existing.find(marker, index)
    block = existing[index:] if end < 0 else existing[index:end]
    return head, "\n" + block.rstrip() + "\n"


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _review_state(golden: dict) -> str:
    """One line saying whether these numbers rest on a reviewed set.

    || Una línea que dice si estos números se apoyan en un set revisado.
    """
    pending = [
        sequence["id"]
        for sequence in golden["sequences"]
        if any(value is None for value in (sequence.get("review") or {}).values())
    ]
    if not pending:
        return (
            "El golden set está **revisado**: las dos casillas de `review` de cada "
            "secuencia están confirmadas por una persona."
        )
    return (
        f"**SIN REVISAR.** El golden set está en `{golden.get('status', 'DRAFT')}`: "
        f"{len(pending)} de {len(golden['sequences'])} secuencias tienen alguna casilla de "
        "`review` sin confirmar. La anotación que decide cada veredicto es **el juicio humano "
        "de si una pregunta depende de la anterior**, así que hasta que alguien la confirme "
        "estos números miden el criterio de quien escribió el archivo."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--through-graph",
        action="store_true",
        help="Run the sequences through the real endpoints. Needs Postgres and spends completions.",
    )
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--attempts", type=int, default=90)
    parser.add_argument(
        "--max-sequences",
        type=int,
        default=None,
        help="Score only the first N sequences. For a smoke run of --through-graph, "
        "which spends a completion per turn.",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Rewrite the Resultados section of evals/MULTITURN_EVAL.md.",
    )
    args = parser.parse_args()

    if not GOLDEN_PATH.exists():
        print(f"{GOLDEN_PATH} not found. Run from ai-service/.", file=sys.stderr)
        return 1
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    sequences = golden["sequences"]
    if args.max_sequences is not None:
        sequences = sequences[: args.max_sequences]
    mode = "through-graph" if args.through_graph else "resolver"
    print(f"Scoring {len(sequences)} sequences in {mode} mode")

    if args.through_graph:
        scores = run_graph_mode(
            sequences, poll_seconds=args.poll_seconds, attempts=args.attempts
        )
    else:
        scores = run_resolver_mode(sequences)
        for score in scores:
            flag = "FALLA" if score.failed else "ok"
            print(
                f"  {flag:<6} {score.sequence_id:<34} t{score.n} "
                f"{score.referent:<10} {score.verdict}"
            )

    summary = summarize(scores)
    print(
        f"\nfalso negativo {_pct(summary['false_negative_rate'])} "
        f"({summary['false_negatives']}/{summary['clear']})  "
        f"falso positivo {_pct(summary['false_positive_rate'])} "
        f"({summary['false_positives']}/{summary['absent']})  "
        f"reescrituras correctas {summary['quality_ok']}/{summary['rewritten_clear']}"
    )
    print(_review_state(golden))

    if args.write_report and args.max_sequences is not None:
        # Un subconjunto no reemplaza el reporte: los mismos títulos de columna
        # con menos turnos detrás se leen como una medición completa.
        # || A subset does not overwrite the report: the same column headers
        # with fewer turns behind them read as a full measurement.
        print("--max-sequences: no se escribe el reporte de una corrida parcial.")
    elif args.write_report:
        REPORT_PATH.write_text(
            render_report(summary, scores, mode=mode, golden=golden), encoding="utf-8"
        )
        print(f"Wrote {REPORT_PATH}")

    # Exit 0 even with failures. This measures a known gap rather than
    # guarding a threshold: a non-zero exit would turn "the resolver misses
    # possessives" into a broken build, and that is the finding, not a break.
    # || Sale 0 incluso con fallas: esto mide un hueco conocido, no custodia
    # un umbral. Un exit distinto de cero volvería el hallazgo un build roto.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

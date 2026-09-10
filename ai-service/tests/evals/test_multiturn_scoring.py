"""The scoring of the multi-turn eval, and the shape of its golden set.

The script that computes ``false_negative_rate`` is not itself measured by
anything, so a sign error in it would publish a wrong number with the same
confidence as a right one. These tests pin the verdict table, and one of them
pins the golden file's shape so a hand-edited sequence cannot silently drop
out of the denominator.

|| El scoring del eval multi-turno y la forma de su golden set. El script que
calcula `false_negative_rate` no lo mide nada, así que un error de signo
publicaría un número equivocado con la misma confianza que uno correcto. Estos
tests fijan la tabla de veredictos, y uno fija la forma del archivo para que
una secuencia editada a mano no se caiga del denominador en silencio.
"""

from __future__ import annotations

import json
from pathlib import Path

import scripts.eval_multiturn as evaluator
from scripts.eval_multiturn import (
    ABSENT,
    AMBIGUOUS,
    CLEAR,
    FALSE_NEGATIVE,
    FALSE_POSITIVE,
    GOLDEN_PATH,
    OK,
    PARTIAL_REFERENT,
    SECTION,
    UNSCORED,
    WRONG_REFERENT,
    facts_for,
    score_turn,
    summarize,
)

REFERENT_LABELS = {CLEAR, ABSENT, AMBIGUOUS}


def _score(referent: str, *, rewritten: bool, named: list[str], expected: list[str]):
    turn = {
        "n": 2,
        "question": "¿Y qué validaciones tiene?",
        "referent": referent,
        "expected_referents": expected,
        "relevant_document_ids": expected,
    }
    return score_turn(
        sequence_id="MT-test",
        turn=turn,
        rewritten=rewritten,
        resolved_question="da igual",
        substituted=named,
    )


def test_clear_and_silent_is_a_false_negative():
    """La dirección que este change existe para poder contar."""
    score = _score(CLEAR, rewritten=False, named=[], expected=["CA014"])
    assert score.verdict == FALSE_NEGATIVE
    assert score.failed


def test_clear_and_exact_referent_is_ok():
    score = _score(CLEAR, rewritten=True, named=["CA014"], expected=["CA014"])
    assert score.verdict == OK
    assert not score.failed


def test_clear_with_an_extra_referent_is_partial_not_ok():
    """Nombrar el correcto no alcanza si además inventó otro.

    Contarlo como `ok` es exactamente el «reescribió» haciéndose pasar por
    «reescribió bien».
    """
    score = _score(CLEAR, rewritten=True, named=["CA014", "CO008"], expected=["CA014"])
    assert score.verdict == PARTIAL_REFERENT
    # Parcial NO es falla: acertó el referente. Pero tampoco es `ok`.
    assert not score.failed


def test_clear_with_only_the_wrong_referent_is_the_worst_verdict():
    score = _score(CLEAR, rewritten=True, named=["CO008"], expected=["CA014"])
    assert score.verdict == WRONG_REFERENT
    assert score.failed


def test_absent_and_rewritten_is_a_false_positive():
    score = _score(ABSENT, rewritten=True, named=["CA014"], expected=[])
    assert score.verdict == FALSE_POSITIVE
    assert score.failed


def test_absent_and_untouched_is_ok():
    score = _score(ABSENT, rewritten=False, named=[], expected=[])
    assert score.verdict == OK


def test_ambiguous_is_never_scored_either_way():
    """Ni acierto ni error: elegir una lectura y evaluarse contra ella no mide."""
    rewrote = _score(AMBIGUOUS, rewritten=True, named=["CA001k"], expected=["CA001k"])
    stayed = _score(AMBIGUOUS, rewritten=False, named=[], expected=["CA001k"])
    assert rewrote.verdict == UNSCORED
    assert stayed.verdict == UNSCORED
    assert not rewrote.failed and not stayed.failed


def test_referents_match_regardless_of_case():
    """`CA001k` lleva minúscula final: comparar exacto lo daría por errado."""
    score = _score(CLEAR, rewritten=True, named=["CA001K"], expected=["CA001k"])
    assert score.verdict == OK


def test_summarize_reports_both_directions_over_their_own_denominators():
    scores = [
        _score(CLEAR, rewritten=False, named=[], expected=["CA014"]),
        _score(CLEAR, rewritten=True, named=["CA014"], expected=["CA014"]),
        _score(ABSENT, rewritten=True, named=["CA014"], expected=[]),
        _score(AMBIGUOUS, rewritten=True, named=["CA014"], expected=["CA014"]),
    ]
    summary = summarize(scores)

    # El denominador de cada dirección es su propio bucket, no el total.
    assert summary["false_negative_rate"] == 0.5  # 1 de 2 `clear`
    assert summary["false_positive_rate"] == 1.0  # 1 de 1 `absent`
    assert summary["turns_scored"] == 3  # los `ambiguous` quedan afuera
    assert summary["ambiguous"] == 1
    assert summary["ambiguous_rewritten"] == 1


def test_summarize_says_none_instead_of_zero_on_an_empty_bucket():
    """Un golden sin `absent` es un golden malo, no un 0% de falsos positivos."""
    summary = summarize([_score(CLEAR, rewritten=True, named=["CA014"], expected=["CA014"])])
    assert summary["false_positive_rate"] is None
    assert summary["false_negative_rate"] == 0.0


def test_facts_for_a_first_turn_are_none():
    """Sin turno anterior no hay hechos, y el resolver tiene que ver eso."""
    assert facts_for(None) is None
    assert facts_for({"question": "x"}) is None


def test_facts_carry_only_the_previous_turn_documents():
    """`last_document_ids` se reemplaza cada turno; no se acumula la secuencia."""
    facts = facts_for({"relevant_document_ids": ["OP004"]})
    assert facts is not None
    assert facts.last_document_ids == ["OP004"]
    assert facts.transaction_codes == ["OP004"]


def test_the_golden_set_keeps_its_shape():
    """Guarda del archivo: una secuencia mal editada se cae del denominador.

    Sin esto, borrar `referent` de un turno lo saca de la métrica sin que
    nada avise, y el `false_negative_rate` mejora por haber medido menos.
    """
    path = Path(__file__).resolve().parents[2] / GOLDEN_PATH
    golden = json.loads(path.read_text(encoding="utf-8"))
    sequences = golden["sequences"]

    assert golden["status"] in {"DRAFT_NOT_REVIEWED", "REVIEWED"}
    assert len(sequences) == len({sequence["id"] for sequence in sequences})

    for sequence in sequences:
        turns = sequence["turns"]
        assert len(turns) >= 2, f"{sequence['id']}: una secuencia de un turno no es multi-turno"
        assert "referent" not in turns[0], f"{sequence['id']}: el primer turno no tiene referente"
        assert [turn["n"] for turn in turns] == list(range(1, len(turns) + 1))
        # Las dos casillas son obligatorias; `confirmed_in` aparece cuando
        # alguien las confirmó y apunta a una entrada de `review_log`.
        review = sequence["review"]
        assert {"questions_are_realistic", "referent_labels_are_correct"} <= set(review)
        assert set(review) <= {
            "questions_are_realistic",
            "referent_labels_are_correct",
            "confirmed_in",
        }
        if review.get("confirmed_in"):
            assert review["confirmed_in"] in {
                entry["id"] for entry in golden.get("review_log", [])
            }, f"{sequence['id']}: `confirmed_in` no apunta a ninguna entrada de review_log"

        for turn in turns[1:]:
            label = turn["referent"]
            assert label in REFERENT_LABELS, f"{sequence['id']}: etiqueta desconocida {label!r}"
            assert turn["question"].strip()
            assert turn["relevant_document_ids"]
            if label in {CLEAR, AMBIGUOUS}:
                assert turn["expected_referents"], (
                    f"{sequence['id']} t{turn['n']}: un `{label}` sin `expected_referents` "
                    "no se puede puntuar"
                )
            else:
                assert "expected_referents" not in turn, (
                    f"{sequence['id']} t{turn['n']}: un `absent` no apunta a ningún referente"
                )
            assert turn.get("why", "").strip(), (
                f"{sequence['id']} t{turn['n']}: la etiqueta es un juicio humano y va con su porqué"
            )


def test_the_golden_set_can_measure_both_directions():
    """Los dos buckets tienen que estar poblados o la medición es media.

    Es la regla que el change existe para imponer: un conjunto con solo
    `clear` mide falsos negativos y vuelve a dejar sin medir la otra
    dirección, que es de donde venimos.
    """
    path = Path(__file__).resolve().parents[2] / GOLDEN_PATH
    golden = json.loads(path.read_text(encoding="utf-8"))
    labels = [
        turn["referent"]
        for sequence in golden["sequences"]
        for turn in sequence["turns"]
        if "referent" in turn
    ]
    assert labels.count(CLEAR) >= 3
    assert labels.count(ABSENT) >= 3
    assert labels.count(AMBIGUOUS) >= 1


def _write_report(tmp_path, monkeypatch, text: str):
    """Apunta el reporte a un archivo temporal con el contenido dado."""
    path = tmp_path / "MULTITURN_EVAL.md"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(evaluator, "REPORT_PATH", path)
    return path


BOTH_SECTIONS = """# Título

Método escrito a mano.

{resolver}

resultados del resolver

{graph}

resultados del grafo
"""


def test_a_run_keeps_the_other_modes_results(tmp_path, monkeypatch):
    """La razón de existir de `_split_report`.

    El eval vecino ya pagó la alternativa: `eval_retrieval.py` con un solo
    `--config` sobrescribió la tabla de cuatro configuraciones.
    """
    _write_report(
        tmp_path,
        monkeypatch,
        BOTH_SECTIONS.format(resolver=SECTION["resolver"], graph=SECTION["through-graph"]),
    )

    head, kept = evaluator._split_report(SECTION["resolver"])

    # El método sobrevive y no arrastra ninguna sección de resultados.
    assert head.startswith("# Título")
    assert "Método escrito a mano." in head
    assert SECTION["resolver"] not in head
    assert SECTION["through-graph"] not in head
    # Y la sección del OTRO modo vuelve entera, para reescribirse detrás.
    assert SECTION["through-graph"] in kept
    assert "resultados del grafo" in kept
    assert "resultados del resolver" not in kept


def test_the_other_direction_keeps_the_resolver_section(tmp_path, monkeypatch):
    _write_report(
        tmp_path,
        monkeypatch,
        BOTH_SECTIONS.format(resolver=SECTION["resolver"], graph=SECTION["through-graph"]),
    )

    head, kept = evaluator._split_report(SECTION["through-graph"])

    assert "Método escrito a mano." in head
    assert SECTION["resolver"] in kept
    assert "resultados del resolver" in kept
    assert "resultados del grafo" not in kept


def test_a_report_with_only_the_method_keeps_all_of_it(tmp_path, monkeypatch):
    """Primera corrida: no hay ninguna sección de resultados todavía."""
    _write_report(tmp_path, monkeypatch, "# Título\n\nSolo método.\n")

    head, kept = evaluator._split_report(SECTION["resolver"])

    assert head == "# Título\n\nSolo método."
    assert kept == ""


def test_no_report_yet_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluator, "REPORT_PATH", tmp_path / "no-existe.md")
    assert evaluator._split_report(SECTION["resolver"]) == ("", "")


def test_rendering_twice_does_not_stack_sections(tmp_path, monkeypatch):
    """Correr el mismo modo dos veces reemplaza, no acumula."""
    _write_report(tmp_path, monkeypatch, "# Título\n\nMétodo.\n")
    golden = {"status": "REVIEWED", "sequences": []}
    scores = [_score(CLEAR, rewritten=True, named=["CA014"], expected=["CA014"])]
    summary = summarize(scores)

    first = evaluator.render_report(summary, scores, mode="resolver", golden=golden)
    (tmp_path / "MULTITURN_EVAL.md").write_text(first, encoding="utf-8")
    second = evaluator.render_report(summary, scores, mode="resolver", golden=golden)

    assert second.count(SECTION["resolver"]) == 1
    assert second.count("Método.") == 1

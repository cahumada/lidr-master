"""The evidence is measured before it becomes a prompt, and what does not fit is reported.

|| La evidencia se mide antes de ser un prompt, y lo que no entra se reporta.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.generation.rag.chunking.base import count_tokens
from app.generation.rag.context_budget import (
    fit_to_budget,
    interleave_by_query,
    render_hit_block,
)
from app.generation.rag.prompt_builder import build_context
from app.generation.rag.schemas import SearchHit


def _hit(**overrides) -> SearchHit:
    defaults = {
        "content_hash": "h1",
        "chunk_id": "CA014::Validaciones::0",
        "document_id": "CA014",
        "document_title": "Coberturas de la poliza individual",
        "section": "Validaciones",
        "bullet_path": "Capital > Limites",
        "module_code": "CA",
        "document_kind": "content",
        "text": "El capital asegurado no puede superar el maximo del plan.",
        "score": 0.031,
        "branches": ["vector"],
        "ranks": {"vector": 1},
    }
    defaults.update(overrides)
    return SearchHit(**defaults)


def _cost(index: int, hit: SearchHit) -> int:
    return count_tokens(render_hit_block(index, hit))


# --- what fits ---------------------------------------------------------


def test_everything_fits_when_the_budget_is_generous():
    hits = [_hit(content_hash=f"h{i}") for i in range(3)]

    budgeted = fit_to_budget(hits, 10_000)

    assert budgeted.kept == hits
    assert budgeted.dropped == []
    assert budgeted.truncated is False
    assert budgeted.dropped_count == 0


def test_the_budget_cuts_whole_hits_from_the_tail():
    hits = [_hit(content_hash=f"h{i}") for i in range(4)]
    budget = _cost(1, hits[0]) + _cost(2, hits[1])

    budgeted = fit_to_budget(hits, budget)

    assert budgeted.kept == hits[:2]
    assert budgeted.dropped == hits[2:]
    assert budgeted.truncated is True
    assert budgeted.dropped_count == 2


def test_a_chunk_is_never_split():
    """Half a business rule reads like a whole one. || Media regla parece entera."""
    hit = _hit(text="una regla larga " * 200)

    budgeted = fit_to_budget([hit], 10)

    assert budgeted.kept == []
    assert budgeted.dropped == [hit]
    # Nothing partial leaked into the kept side.
    assert budgeted.tokens_used == 0


def test_a_single_oversized_hit_leaves_the_context_empty_but_counted():
    """Evidence found and none of it usable is NOT the same as finding nothing.

    || Evidencia encontrada y ninguna usable NO es lo mismo que no encontrar nada.
    """
    hits = [_hit(content_hash=f"h{i}", text="regla " * 500) for i in range(3)]

    budgeted = fit_to_budget(hits, 50)

    assert budgeted.kept == []
    assert budgeted.dropped_count == 3
    assert budgeted.truncated is True


# --- what is counted ---------------------------------------------------


def test_the_count_covers_the_rendered_block_not_the_bare_text():
    """The header and the breadcrumb are tokens the model reads.

    || El encabezado y el breadcrumb son tokens que el modelo lee.
    """
    hit = _hit()

    assert _cost(1, hit) > count_tokens(hit.text)


def test_what_is_measured_is_what_is_sent():
    """One renderer, so the counted text and the prompt text cannot drift.

    || Un solo renderer, así el texto contado y el del prompt no se separan.
    """
    hits = [_hit(content_hash=f"h{i}") for i in range(3)]

    budgeted = fit_to_budget(hits, 10_000)
    context = build_context(budgeted.kept)

    for index, hit in enumerate(budgeted.kept, start=1):
        assert render_hit_block(index, hit) in context


def test_the_kept_prefix_costs_what_was_counted():
    hits = [_hit(content_hash=f"h{i}") for i in range(3)]
    budget = _cost(1, hits[0]) + _cost(2, hits[1])

    budgeted = fit_to_budget(hits, budget)

    assert budgeted.tokens_used == budget


# --- the order the budget consumes -------------------------------------


def test_one_group_is_the_identity():
    """A single ranked run is already ordered; reordering it destroys the order.

    || Una sola corrida rankeada ya viene ordenada; reordenarla la destruye.
    """
    hits = [_hit(content_hash=f"h{i}") for i in range(4)]

    assert interleave_by_query([hits]) == hits


def test_no_groups_is_empty():
    assert interleave_by_query([]) == []


def test_a_compound_question_keeps_evidence_from_both_halves():
    """The failure this exists to prevent: half the question answered with confidence.

    || El fallo que esto evita: media pregunta respondida con aplomo.
    """
    left = [_hit(content_hash=f"a{i}", document_id="CA014") for i in range(5)]
    right = [_hit(content_hash=f"b{i}", document_id="CO001") for i in range(5)]

    ordered = interleave_by_query([left, right])
    budgeted = fit_to_budget(ordered, sum(_cost(i + 1, h) for i, h in enumerate(ordered[:4])))

    kept_documents = {hit.document_id for hit in budgeted.kept}
    assert kept_documents == {"CA014", "CO001"}
    assert budgeted.truncated is True


def test_interleaving_alternates_and_drains_the_longer_group():
    left = [_hit(content_hash=f"a{i}") for i in range(3)]
    right = [_hit(content_hash="b0")]

    ordered = interleave_by_query([left, right])

    assert [hit.content_hash for hit in ordered] == ["a0", "b0", "a1", "a2"]


def test_a_budget_of_zero_is_rejected_at_startup():
    """A 0 does not mean "no limit" -- it would mean an empty context.

    || Un 0 no significa «sin límite»: significaría contexto vacío.
    """
    with pytest.raises(ValidationError):
        Settings(ANSWER_MAX_CONTEXT_TOKENS=0)

    with pytest.raises(ValidationError):
        Settings(ANSWER_MAX_CONTEXT_TOKENS=-1)


def _baseline_block(**overrides) -> str:
    return render_hit_block(1, _hit(**overrides))


def test_active_or_unresolved_status_renders_like_before_this_change():
    baseline = _baseline_block()

    assert render_hit_block(1, _hit(window_status="Activo")) == baseline
    assert render_hit_block(1, _hit(window_status=None)) == baseline


def test_a_restricted_status_adds_the_declared_warning_line():
    block = render_hit_block(1, _hit(window_status="Acceso restringido"))

    assert "Estado de la ventana (declarado): Acceso restringido" in block
    assert "baja" not in block.lower()


def test_fit_to_budget_counts_the_warning_line():
    active = _hit(content_hash="active", window_status="Activo")
    restricted = _hit(
        content_hash="restricted",
        window_status="Acceso restringido",
        text=active.text,
    )
    budget = _cost(1, active) + 1

    active_budgeted = fit_to_budget([active], budget)
    restricted_budgeted = fit_to_budget([restricted], budget)

    assert active_budgeted.kept == [active]
    assert restricted_budgeted.kept == []
    assert restricted_budgeted.dropped == [restricted]


def test_a_hit_found_by_two_sub_queries_enters_once():
    shared = _hit(content_hash="shared")
    left = [shared, _hit(content_hash="a1")]
    right = [_hit(content_hash="b0"), shared]

    ordered = interleave_by_query([left, right])

    assert [hit.content_hash for hit in ordered] == ["shared", "b0", "a1"]
    assert len(ordered) == 3

"""Tests for fusion, the identifier detector and the SQL of each branch.

All of it verifiable without Postgres, so it runs on every `pytest`. What needs
a real database -- whether the branches actually return what they should -- is in
`tests/store/test_store_integration.py`.

|| Tests de la fusión, el detector de identificadores y el SQL de cada rama.
Todo verificable sin Postgres, así que corre en cada `pytest`. Lo que necesita
base de verdad —si las ramas realmente devuelven lo que deben— está en
`tests/store/test_store_integration.py`.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy.dialects import postgresql

from app.generation.rag.retrieval.fusion import (
    DEFAULT_RRF_K,
    cap_per_group,
    reciprocal_rank_fusion,
)
from app.generation.rag.retrieval.hybrid import DEFAULT_BRANCH_LIMIT, identifier_terms
from app.generation.rag.store.repository import (
    SearchFilters,
    build_exact_statement,
    build_lexical_statement,
)


def sql_of(statement) -> str:
    return re.sub(r"\s+", " ", str(statement.compile(dialect=postgresql.dialect())))


def ranking(*keys: str) -> list[str]:
    return list(keys)


def fuse(rankings: dict[str, list[str]], **kwargs):
    return reciprocal_rank_fusion(rankings, key=lambda item: item, **kwargs)


# --- The constant --------------------------------------------------------------


def test_the_rrf_constant_is_the_courses():
    """60, from Cormack et al., the same as the course's `DEFAULT_RRF_K`."""
    assert DEFAULT_RRF_K == 60


# --- What fusion is for --------------------------------------------------------


def test_appearing_in_two_branches_beats_winning_one():
    """The whole point of the fusion. `b` is second and third; `c` is first in a
    single branch. `b` wins: 1/62 + 1/63 = 0.0320 against 1/61 = 0.0164."""
    fused = fuse({"vector": ranking("a", "b"), "lexical": ranking("c", "a", "b")})

    assert [item.key for item in fused] == ["a", "b", "c"]


def test_a_result_carries_the_branches_that_found_it():
    """A chunk found by two branches is a different kind of answer than one
    found by one, and the reader should be able to tell."""
    fused = fuse({"vector": ranking("a"), "exact": ranking("a")})

    assert fused[0].branches == ["vector", "exact"]
    assert fused[0].ranks == {"vector": 1, "exact": 1}


def test_the_score_is_the_sum_of_reciprocal_ranks():
    fused = fuse({"vector": ranking("a"), "lexical": ranking("x", "a")})

    assert fused[0].score == pytest.approx(1 / 61 + 1 / 62)


def test_no_duplicates_when_a_chunk_is_in_every_branch():
    fused = fuse({"v": ranking("a"), "l": ranking("a"), "e": ranking("a")})

    assert len(fused) == 1
    assert len(fused[0].branches) == 3


def test_an_empty_branch_does_not_break_the_fusion():
    fused = fuse({"vector": ranking("a", "b"), "lexical": []})

    assert [item.key for item in fused] == ["a", "b"]


def test_no_branches_at_all_yields_nothing():
    assert fuse({}) == []


def test_every_branch_weighs_the_same():
    """The course deliberately has no per-branch weights: the point of RRF is
    that positional consensus decides. Two results first in one branch each must
    tie."""
    fused = fuse({"vector": ranking("a"), "lexical": ranking("b")})

    assert fused[0].score == pytest.approx(fused[1].score)


def test_ties_break_deterministically():
    """A metric that moves between runs is useless, so equal scores order by key."""
    first = fuse({"vector": ranking("b"), "lexical": ranking("a")})
    second = fuse({"lexical": ranking("a"), "vector": ranking("b")})

    assert [item.key for item in first] == ["a", "b"]
    assert [item.key for item in second] == ["a", "b"]


def test_a_larger_k_flattens_the_curve():
    """That is what k is for: a big k forces a result to rank well across
    branches, a small one lets one first place dominate."""
    rankings = {"vector": ranking("a", "b", "c"), "lexical": ranking("b", "c", "a")}
    small = fuse(rankings, k=1)
    large = fuse(rankings, k=1000)

    spread_small = small[0].score - small[-1].score
    spread_large = large[0].score - large[-1].score
    assert spread_large < spread_small


def test_the_limit_trims_the_fused_list():
    fused = fuse({"vector": ranking("a", "b", "c")}, limit=2)
    assert len(fused) == 2


# --- The per-document cap -------------------------------------------------------


def document_of(chunk_id: str) -> str:
    return chunk_id.split("::")[0]


def test_no_cap_lets_one_document_take_everything():
    """`AGL009` taking all 10 results for a question about `AGL009`'s logic is
    the right answer, so the default does not trim."""
    fused = fuse({"vector": ranking(*[f"AGL009::x::{i}" for i in range(5)])})

    capped = cap_per_group(fused, document_of, cap=None, limit=5)

    assert len(capped) == 5
    assert {document_of(item.key) for item in capped} == {"AGL009"}


def test_a_cap_trims_and_the_next_ones_fill_in():
    fused = fuse(
        {"vector": ranking("A::x::1", "A::x::2", "A::x::3", "B::y::1", "C::z::1")}
    )

    capped = cap_per_group(fused, document_of, cap=1, limit=3)

    assert [item.key for item in capped] == ["A::x::1", "B::y::1", "C::z::1"]


def test_the_cap_never_returns_more_than_the_limit():
    fused = fuse({"vector": ranking(*[f"D{i}::x::1" for i in range(10)])})
    assert len(cap_per_group(fused, document_of, cap=2, limit=4)) == 4


def test_a_cap_larger_than_what_a_document_has_changes_nothing():
    fused = fuse({"vector": ranking("A::x::1", "B::y::1")})
    capped = cap_per_group(fused, document_of, cap=5, limit=10)
    assert [item.key for item in capped] == ["A::x::1", "B::y::1"]


def test_a_narrow_candidate_pool_starves_the_cap():
    """With `cap=1` the answer holds at most as many documents as the pool has
    distinct ones. 30 chunks concentrated in 6 documents return 6 results for a
    `limit=10`, and the 4 empty places are the defect that raised
    `DEFAULT_BRANCH_LIMIT`: 7 of the 26 human-authored questions came back short.
    The filling is not broken -- there is nothing left to fill with."""
    pool = [f"D{i % 6}::x::{i}" for i in range(30)]
    fused = fuse({"vector": ranking(*pool)})

    capped = cap_per_group(fused, document_of, cap=1, limit=10)

    assert len(capped) == 6
    assert len({document_of(item.key) for item in capped}) == 6


def test_a_wide_candidate_pool_fills_the_limit():
    """The same 6-document concentration, but the pool now reaches further and
    holds 12 documents. This is what raising the branch limit buys."""
    pool = [f"D{i % 6}::x::{i}" for i in range(30)]
    pool += [f"E{i}::y::1" for i in range(6)]
    fused = fuse({"vector": ranking(*pool)})

    capped = cap_per_group(fused, document_of, cap=1, limit=10)

    assert len(capped) == 10


def test_the_branch_limit_leaves_room_for_the_cap():
    """Not a taste setting. Measured over the 26 human-authored questions at
    `cap=1`, `k=10`: 30 left 7 questions short, 100 left none, 300 changed
    nothing. It has to stay well above any plausible `k`."""
    assert DEFAULT_BRANCH_LIMIT >= 100


# --- The identifier detector -----------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # Transaction codes, the way users talk about these documents.
        ("CAC011", ["CAC011"]),
        ("que dice CAC011 sobre la poliza", ["CAC011"]),
        ("BC005_k", ["BC005_k"]),
        ("VI7501_A", ["VI7501_A"]),
        # Table and column names: the full-text tokenizer splits these on the
        # underscore and the embedding does not see them at all.
        ("tabla premium_mo", ["premium_mo"]),
        ("campo nReceipt", ["nReceipt"]),
        ("TIN_AllowDoubAccIss", ["TIN_AllowDoubAccIss"]),
        # Error codes.
        ("codigo de error 10208", ["10208"]),
        ("736024", ["736024"]),
        # Repeated: counted once, so it does not weigh twice.
        ("CAC011 y CAC011", ["CAC011"]),
    ],
)
def test_identifiers_are_detected(query, expected):
    assert identifier_terms(query) == expected


@pytest.mark.parametrize(
    "query",
    [
        "como se emite una poliza nueva",
        "validaciones de la fecha de vigencia",
        "que pasa si el importe de ajuste supera la comision neta",
        "",
        "   ",
    ],
)
def test_a_natural_language_question_detects_nothing(query):
    """Most queries are questions, and running the exact branch on those is
    wasted work."""
    assert identifier_terms(query) == []


@pytest.mark.parametrize("query", ["la reserva del 2026", "poliza de 1998", "ejercicio 2025"])
def test_a_year_is_not_an_error_code(query):
    """A four-digit number is ambiguous. Every error code in this corpus falls
    outside 1900-2099."""
    assert identifier_terms(query) == []


def test_punctuation_around_a_code_does_not_hide_it():
    assert identifier_terms("¿que hace (CAC011)?") == ["CAC011"]
    assert identifier_terms("ver CAC011.") == ["CAC011"]


# --- The SQL of each branch --------------------------------------------------------


def filters() -> SearchFilters:
    return SearchFilters("acme", "v1")


def test_the_lexical_branch_combines_terms_with_or():
    """`plainto_tsquery` ANDs them, which is why `codigo de error 10208` came
    back empty even though `10208` is in two chunks."""
    sql = sql_of(build_lexical_statement("codigo de error 10208", filters(), limit=5))

    assert "plainto_tsquery" not in sql
    assert "to_tsquery" in sql
    assert "array_to_string" in sql, "the OR is built from the query's own lexemes"


def test_the_lexical_branch_ranks_by_cover_density():
    sql = sql_of(build_lexical_statement("poliza", filters(), limit=5))
    assert "ts_rank_cd" in sql
    assert "ORDER BY score DESC" in sql


def test_the_lexical_branch_keeps_the_structural_filters():
    """Both branches must narrow the same way, or the fusion compares different
    candidate spaces."""
    sql = sql_of(
        build_lexical_statement("poliza", SearchFilters("acme", "v1", module_code="DMECAR"), limit=5)
    )
    assert "chunks.tenant_id = " in sql
    assert "chunks.doc_version = " in sql
    assert "chunks.module_code = " in sql


def test_the_exact_branch_asks_the_three_questions():
    """Is it a document id, is it a field name, does the text contain it."""
    sql = sql_of(build_exact_statement(["CAC011"], filters(), limit=5))

    assert "chunks.document_id IN" in sql
    assert "chunks.field IN" in sql
    assert "chunks.text ILIKE" in sql


def test_the_exact_branch_puts_the_owning_document_first():
    """Asking for `CAC011` is asking for that document, not for one that
    mentions it in passing."""
    sql = sql_of(build_exact_statement(["CAC011"], filters(), limit=5))
    order_by = sql.split("ORDER BY", 1)[1]
    assert "document_id IN" in order_by


def test_the_exact_branch_also_keeps_the_filters():
    sql = sql_of(build_exact_statement(["CAC011"], filters(), limit=5))
    assert "chunks.tenant_id = " in sql
    assert "chunks.doc_version = " in sql

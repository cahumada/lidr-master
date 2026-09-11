"""NG_IDENTI only for type 10; other types are ignored and counted.

|| NG_IDENTI solo para el tipo 10; los demás se ignoran y se cuentan.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.generation.rag.business_db.models import TableDictionary
from app.generation.rag.business_db.resolve import anchored_codes, resolve_context
from app.generation.rag.navigation import NavigationTree
from app.generation.rag.schemas import SearchHit


def _tree() -> NavigationTree:
    return NavigationTree(
        [
            ("MA0007", "MENU", "Bancos", "10", "", "1", "7"),
            ("COL504", "MENU", "Libro de recaudación", "3", "", "1", "2"),
            ("CA014", "MENU", "Coberturas", "1", "", "1", "0"),
        ]
    )


def _hit(document_id: str) -> SearchHit:
    return SearchHit(
        content_hash=document_id,
        chunk_id=f"{document_id}::Función::0",
        document_id=document_id,
        text="texto",
        score=0.1,
    )


def test_anchored_codes_are_the_kept_hits_deduplicated_and_capped():
    kept, dropped = anchored_codes(
        [_hit("MA0007"), _hit("MA0007"), _hit("CA014"), _hit("COL504")],
        max_codes=2,
    )
    assert kept == ["MA0007", "CA014"]
    assert dropped == ["COL504"]


def test_type_10_resolves_the_table_and_other_types_are_ignored(monkeypatch):
    monkeypatch.setattr(
        "app.generation.rag.business_db.resolve.read_run_created_at",
        lambda *a, **k: datetime(2026, 9, 9, tzinfo=UTC),
    )
    monkeypatch.setattr(
        "app.generation.rag.business_db.resolve.read_table_dictionary",
        lambda *a, **k: TableDictionary(
            table_name="TABLE7", description_es="Bancos", columns=[]
        ),
    )
    monkeypatch.setattr(
        "app.generation.rag.business_db.resolve.read_catalog_rows",
        lambda *a, **k: ((), False),
    )

    context = resolve_context(
        database_url="postgresql://unused",
        tenant="t",
        env="PROD",
        run_id="r",
        codes=["MA0007", "COL504", "CA014", "ZZ999"],
        tree=_tree(),
        max_rows=10,
    )
    by_code = {item.code: item for item in context.resolutions}
    assert by_code["MA0007"].table_name == "TABLE7"
    assert by_code["MA0007"].outcome == "table_not_loaded"
    assert by_code["COL504"].outcome == "ng_identi_ignored_by_type"
    assert by_code["CA014"].outcome == "no_maintained_table"
    assert by_code["ZZ999"].outcome == "not_in_run"


def test_a_missing_dictionary_is_table_not_in_dictionary(monkeypatch):
    monkeypatch.setattr(
        "app.generation.rag.business_db.resolve.read_run_created_at",
        lambda *a, **k: datetime(2026, 9, 9, tzinfo=UTC),
    )
    monkeypatch.setattr(
        "app.generation.rag.business_db.resolve.read_table_dictionary",
        lambda *a, **k: None,
    )

    context = resolve_context(
        database_url="postgresql://unused",
        tenant="t",
        env="PROD",
        run_id="r",
        codes=["MA0007"],
        tree=_tree(),
        max_rows=10,
    )
    assert context.resolutions[0].outcome == "table_not_in_dictionary"
    assert context.complete is False

"""The block names its run, trims in DROP_ORDER, and never splits a row.

|| El bloque nombra su corrida, recorta en DROP_ORDER y nunca parte una fila.
"""

from __future__ import annotations

from datetime import date

from app.generation.rag.business_db.models import (
    BusinessDbContext,
    CatalogRow,
    CodeResolution,
    ColumnDictionary,
    TableDictionary,
)
from app.generation.rag.business_db.render import DROP_ORDER, block_text, render_block
from app.generation.rag.chunking.base import count_tokens


def _dictionary() -> TableDictionary:
    return TableDictionary(
        table_name="TABLE7",
        description_es="Bancos del sistema",
        columns=[
            ColumnDictionary(name="NCODE", description="Código del banco"),
            ColumnDictionary(name="SDESCRIPT", description="Nombre"),
        ],
    )


def _resolution(*codes: str, rows: int = 5) -> list[CodeResolution]:
    return [
        CodeResolution(
            code=code,
            outcome="resolved",
            causes=["resolved"],
            table_name="TABLE7",
            window_type="10",
            window_type_name="Tabla general",
            window_status="Activo",
            window_description="Bancos",
            ng_identi=7,
            dictionary=_dictionary(),
            rows=[
                CatalogRow(values={"NCODE": str(index), "SDESCRIPT": f"Banco {index} " + ("x" * 20)})
                for index in range(rows)
            ],
            rows_valid=rows,
            rows_shown=rows,
            rows_fetched=rows,
            mechanism="status",
        )
        for code in codes
    ]


def test_the_block_names_its_run_and_is_another_authority():
    context = render_block(
        BusinessDbContext(
            run_id="20260909_214921",
            env="PROD",
            as_of=date(2026, 9, 9),
            resolutions=_resolution("MA0007"),
        ),
        budget=4000,
    )
    text = block_text(context)
    assert text is not None
    assert "20260909_214921" in text
    assert "PROD" in text
    assert "NO es documentación funcional" in text
    assert "reportá la diferencia" in text
    assert "### MA0007" in text


def test_drop_order_is_rows_then_columns_then_table():
    assert DROP_ORDER == ("rows_tail", "column_descriptions", "table_description")

    full = BusinessDbContext(
        run_id="r",
        env="PROD",
        resolutions=_resolution("MA0007", rows=20),
    )
    unlimited = render_block(full, budget=20_000)
    full_cost = unlimited.tokens_used
    fat = render_block(full, budget=max(full_cost - 80, 200))
    text = block_text(fat)
    assert text is not None
    assert "Bancos" in text
    assert fat.resolutions[0].rows_shown < fat.resolutions[0].rows_valid
    assert fat.resolutions[0].rows_shown > 0
    assert "se muestran" in text
    assert "dropped_by_budget" in fat.resolutions[0].causes


def test_a_trimmed_list_carries_the_real_count():
    full = BusinessDbContext(
        run_id="r",
        env="PROD",
        resolutions=_resolution("MA0007", rows=12),
    )
    unlimited = render_block(full, budget=20_000)
    context = render_block(full, budget=max(unlimited.tokens_used - 40, 250))
    text = block_text(context) or ""
    shown = context.resolutions[0].rows_shown
    assert 0 < shown < 12
    assert f"{shown}" in text
    assert "12" in text
    assert "se muestran" in text


def test_a_row_is_never_split():
    context = render_block(
        BusinessDbContext(
            run_id="r",
            env="PROD",
            resolutions=_resolution("MA0007", rows=8),
        ),
        budget=200,
    )
    text = block_text(context) or ""
    for line in text.splitlines():
        if line.startswith("|") and "---" not in line and "NCODE" not in line:
            assert "Banco" in line or line.count("|") >= 3


def test_window_declaration_survives_a_tight_budget():
    context = render_block(
        BusinessDbContext(
            run_id="r",
            env="PROD",
            resolutions=_resolution("MA0007", rows=8),
        ),
        budget=80,
    )
    text = block_text(context) or ""
    assert "### MA0007" in text
    assert "Tabla general" in text


def test_zero_budget_emits_nothing_and_counts_the_drop():
    context = render_block(
        BusinessDbContext(
            run_id="r",
            env="PROD",
            resolutions=_resolution("MA0007"),
        ),
        budget=0,
    )
    assert context.block_emitted is False
    assert block_text(context) is None
    assert "dropped_by_budget" in context.resolutions[0].causes
    assert context.complete is False


def test_completeness_section_names_each_cause():
    context = render_block(
        BusinessDbContext(
            run_id="r",
            env="PROD",
            resolutions=[
                CodeResolution(
                    code="MA0099",
                    outcome="table_not_loaded",
                    causes=["table_not_loaded"],
                    table_name="TABLE99",
                    window_type_name="Tabla general",
                    window_description="Ausente",
                )
            ],
        ),
        budget=2000,
    )
    text = block_text(context) or ""
    assert "Qué no se pudo traer" in text
    assert "table_not_loaded" in text
    assert "TABLE99" in text


def test_complete_context_says_everything_arrived():
    context = render_block(
        BusinessDbContext(
            run_id="r",
            env="PROD",
            resolutions=_resolution("MA0007", rows=2),
        ),
        budget=4000,
    )
    text = block_text(context) or ""
    assert "Se trajo todo lo que la base declara" in text
    assert count_tokens(text) == context.tokens_used

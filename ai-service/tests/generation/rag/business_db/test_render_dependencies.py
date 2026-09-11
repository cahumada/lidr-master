"""The dependency section: what it says, what it never drops, what it counts.

|| La sección de dependencias: qué dice, qué nunca recorta, qué cuenta.
"""

from __future__ import annotations

from app.generation.rag.business_db.models import (
    BusinessDbContext,
    CodeResolution,
    DependencyTable,
)
from app.generation.rag.business_db.render import DROP_ORDER, block_text, render_block


def _table(name: str, role: str = "unknown", hits: int = 3, via: list[str] | None = None):
    return DependencyTable(
        table_name=name,
        role=role,
        role_reason="regla de prueba",
        via_routines=via or ["INSPOSTCA014", "REACA014"],
        routine_hits=hits,
        routine_total=3,
        fan_in=1037,
    )


def _context(tables: list[DependencyTable], total: int | None = None) -> BusinessDbContext:
    return BusinessDbContext(
        run_id="20260909_214921",
        env="PROD",
        resolutions=[
            CodeResolution(
                code="CA014",
                outcome="no_maintained_table",
                causes=["no_maintained_table"],
                window_description="Alta de coberturas",
                dependency_tables=tables,
                dependency_tables_total=total if total is not None else len(tables),
            )
        ],
    )


class TestSection:
    def test_names_tables_roles_and_routines(self) -> None:
        context = render_block(_context([_table("COVER")]), budget=4096)
        text = block_text(context) or ""
        assert "COVER" in text
        assert "rol no declarado" in text
        assert "INSPOSTCA014" in text and "REACA014" in text

    def test_says_the_order_is_not_a_hierarchy(self) -> None:
        context = render_block(_context([_table("COVER")]), budget=4096)
        text = block_text(context) or ""
        assert "no es una jerarquía de importancia declarada" in text

    def test_warns_about_unknown_roles(self) -> None:
        context = render_block(_context([_table("COVER")]), budget=4096)
        text = block_text(context) or ""
        assert "No lo supongas." in text

    def test_a_declared_role_does_not_trigger_the_warning(self) -> None:
        context = render_block(_context([_table("POLICY_HIS", role="historical")]), budget=4096)
        text = block_text(context) or ""
        assert "histórica" in text
        assert "No lo supongas." not in text

    def test_capped_list_reports_the_real_total(self) -> None:
        context = render_block(_context([_table("COVER")], total=38), budget=4096)
        text = block_text(context) or ""
        assert "38" in text
        assert "se muestran 1" in text

    def test_no_routine_names_the_code(self) -> None:
        base = _context([])
        base.resolutions[0].causes.append("no_dependency_routine")
        text = block_text(render_block(base, budget=4096)) or ""
        assert "Ninguna rutina de la base nombra este código." in text

    def test_edges_not_built_is_said_out_loud(self) -> None:
        base = _context([])
        base.resolutions[0].causes.append("edges_not_built")
        rendered = render_block(base, budget=4096)
        text = block_text(rendered) or ""
        assert "no están construidas para esta corrida" in text
        assert rendered.complete is False


class TestTrim:
    def test_tables_are_dropped_before_rows(self) -> None:
        assert DROP_ORDER[0] == "dependency_tables_tail"
        assert DROP_ORDER.index("dependency_tables_tail") < DROP_ORDER.index("rows_tail")

    def test_drops_from_the_tail_of_the_coverage_order(self) -> None:
        tables = [
            _table("COVER", hits=3),
            _table("PRODUCT_LI", hits=2),
            _table("NOPAYROLL", hits=1),
        ]
        rendered = render_block(_context(tables), budget=120)
        kept = [t.table_name for t in rendered.resolutions[0].dependency_tables]
        assert kept[0] == "COVER"
        assert "NOPAYROLL" not in kept

    def test_never_drops_the_last_table(self) -> None:
        tables = [_table("COVER", hits=3), _table("NOPAYROLL", hits=1)]
        rendered = render_block(_context(tables), budget=1)
        assert len(rendered.resolutions[0].dependency_tables) >= 1

    def test_a_kept_table_never_loses_its_routines(self) -> None:
        tables = [_table("COVER", hits=3), _table("NOPAYROLL", hits=1)]
        rendered = render_block(_context(tables), budget=1)
        for table in rendered.resolutions[0].dependency_tables:
            assert table.via_routines

    def test_trimming_is_counted(self) -> None:
        tables = [_table(f"T{i}", hits=3 - (i % 3)) for i in range(8)]
        rendered = render_block(_context(tables), budget=100)
        resolution = rendered.resolutions[0]
        if len(resolution.dependency_tables) < 8:
            assert "dependency_tables_capped" in resolution.causes
            assert rendered.complete is False

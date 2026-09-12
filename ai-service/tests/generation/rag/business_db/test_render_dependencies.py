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


class TestACapIsDeclaredNotIncomplete:
    """A stated, counted, ordered truncation is not a mute absence.

    The section says "Tablas que toca: 17, se muestran 12" and the twelve are
    the highest-coverage ones. Measured, the cap bit 26% of the codes that have
    tables and a turn anchors about ten of them, so counting it as
    incompleteness raised the notice on nearly every answer -- and then
    `edges_not_built` goes unread on the day it matters.

    || Un recorte declarado, contado y ordenado no es una ausencia muda.
    """

    def _capped(self) -> BusinessDbContext:
        return _context([_table("COVER")], total=17)

    def test_a_cap_alone_leaves_the_context_complete(self) -> None:
        context = self._capped()
        context.resolutions[0].causes.append("dependency_tables_capped")

        assert context.with_completeness().complete is True

    def test_the_cap_is_still_named_in_the_closing_section(self) -> None:
        # Not incompleteness, and still not silent: a reader scanning the
        # section should not have to re-read every table list.
        # || No es incompletitud, y tampoco es silencio.
        context = self._capped()
        context.resolutions[0].causes.append("dependency_tables_capped")
        text = block_text(render_block(context, budget=4096)) or ""

        assert "dependency_tables_capped" in text

    def test_a_mute_absence_still_raises_it(self) -> None:
        context = self._capped()
        context.resolutions[0].causes.append("edges_not_built")

        assert context.with_completeness().complete is False

    def test_the_two_sets_do_not_overlap(self) -> None:
        from app.generation.rag.business_db.models import (
            DECLARED_TRUNCATION,
            INCOMPLETE_OUTCOMES,
        )

        assert not (DECLARED_TRUNCATION & INCOMPLETE_OUTCOMES)


class TestDroppedCodesAreNamed:
    """`dropped_codes` is the one incompleteness with no resolution to carry it.

    The block already named it; the console banner did not, and fell back to
    "quedó algo afuera" for the commonest case there is.

    || `dropped_codes` es la única incompletitud sin resolución que la lleve.
    """

    def test_the_block_names_the_dropped_codes(self) -> None:
        context = _context([_table("COVER")])
        context.dropped_codes = ["GIL215", "POLICIES_GENERAL"]
        rendered = render_block(context.with_completeness(), budget=4096)
        text = block_text(rendered) or ""

        assert "GIL215" in text
        assert "POLICIES_GENERAL" in text
        assert rendered.complete is False

    def test_dropped_codes_alone_make_the_context_incomplete(self) -> None:
        # No resolution carries a cause here: the cap dropped the codes before
        # anything was resolved for them.
        # || Ninguna resolución lleva causa: el tope los descartó antes.
        context = _context([_table("COVER")])
        context.dropped_codes = ["GIL215"]

        recomputed = context.with_completeness()

        assert recomputed.complete is False
        assert all("dropped_by_budget" not in r.causes for r in recomputed.resolutions)


def test_the_code_cap_matches_the_answer_limit() -> None:
    """A cap below the retrieval default drops codes on every single answer.

    `/answer` defaults to `limit=10` with `max_per_document=1`, so ten hits are
    ten distinct documents. A cap of 8 marked every context incomplete, and a
    notice that always fires is a notice nobody reads.

    || Un tope por debajo del default de recuperación recorta códigos en TODAS
    las respuestas, y un aviso que salta siempre no lo lee nadie.
    """
    from app.config import Settings
    from app.generation.rag.schemas import AnswerRequest

    cap = Settings.model_fields["BUSINESS_DB_CONTEXT_MAX_CODES"].default
    limit = AnswerRequest.model_fields["limit"].default

    assert cap >= limit


class TestTableDescription:
    """A name alone does not inform: CESSION_NPR vs CESSION_PR is the answer.

    || Un nombre solo no informa: CESSION_NPR contra CESSION_PR es la respuesta.
    """

    def test_a_table_with_a_dictionary_entry_says_what_it_is(self) -> None:
        table = _table("CESSION_NPR")
        table.description = "Cesiones de primas no proporcionales de reaseguro."
        text = block_text(render_block(_context([table]), budget=4096)) or ""

        assert "Cesiones de primas no proporcionales de reaseguro." in text

    def test_a_table_without_one_is_still_emitted(self) -> None:
        # The dependency is declared either way; silence would lose a fact.
        # || La dependencia está declarada igual; callarla perdería un hecho.
        table = _table("SIN_FICHA")
        table.description = None
        text = block_text(render_block(_context([table]), budget=4096)) or ""

        assert "SIN_FICHA" in text

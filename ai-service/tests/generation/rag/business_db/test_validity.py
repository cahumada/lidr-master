"""The four §4.4 cases, NULL vs [], and dates that do not parse.

|| Los cuatro casos de §4.4, NULL vs [], y fechas que no parsean.
"""

from __future__ import annotations

from datetime import date

from app.generation.rag.business_db.models import CatalogRow, ColumnDictionary
from app.generation.rag.business_db.validity import (
    apply_status_filter,
    apply_validity,
    declared_mechanism,
    normalize_status,
    parse_row_date,
    status_catalog_is_foreign,
    status_catalog_is_table26,
)


def _cols(*names: str, descriptions: dict[str, str] | None = None) -> list[ColumnDictionary]:
    notes = descriptions or {}
    return [ColumnDictionary(name=name, description=notes.get(name)) for name in names]


def _row(**values: str | None) -> CatalogRow:
    return CatalogRow(values=values)


def test_status_only_is_status():
    assert declared_mechanism(_cols("SSTATREGT", "SDESCRIPT")) == "status"


def test_full_period_is_period():
    assert declared_mechanism(_cols("DEFFECDATE", "DNULLDATE", "NCODE")) == "period"


def test_both_mechanisms_is_both():
    assert declared_mechanism(_cols("SSTATREGT", "DEFFECDATE", "DNULLDATE")) == "both"


def test_half_pair_is_none_not_a_half_predicate():
    """POLICY / CHEQUES / BANK_MOV: presence is not the mechanism.

    || La presencia de la columna no es el mecanismo.
    """
    assert declared_mechanism(_cols("DEFFECDATE", "SDESCRIPT")) == "none"
    assert declared_mechanism(_cols("DNULLDATE", "SDESCRIPT")) == "none"
    assert declared_mechanism(_cols("SSTATREGT", "DEFFECDATE")) == "none"


def test_empty_columns_is_none_null_columns_is_unknown():
    """NULL is 'not extracted'; [] is 'the table has none'. §12.

    || NULL es «no se extrajeron»; [] es «la tabla no tiene».
    """
    assert declared_mechanism(None) == "unknown"
    assert declared_mechanism([]) == "none"


def test_status_filter_keeps_only_one_and_counts_a_four():
    rows = [
        _row(SSTATREGT="1", SDESCRIPT="activo"),
        _row(SSTATREGT="3", SDESCRIPT="restringido"),
        _row(SSTATREGT="4", SDESCRIPT="error"),
        _row(SSTATREGT="1    ", SDESCRIPT="padded"),
    ]
    counts = apply_validity(
        rows, mechanism="status", as_of=date(2026, 9, 9), apply_status=True
    )

    assert [row.values["SDESCRIPT"] for row in counts.kept] == ["activo", "padded"]
    assert counts.status_normalized_from_4 == 1


def test_period_filter_uses_as_of_not_now():
    rows = [
        _row(DEFFECDATE="2024-01-01", DNULLDATE="2025-01-01", NCODE="old"),
        _row(DEFFECDATE="2024-01-01", DNULLDATE=None, NCODE="open"),
        _row(DEFFECDATE="2026-12-01", DNULLDATE=None, NCODE="future"),
    ]
    counts = apply_validity(
        rows, mechanism="period", as_of=date(2025, 6, 1), apply_status=False
    )

    assert [row.values["NCODE"] for row in counts.kept] == ["open"]


def test_explicit_as_of_beats_a_later_run_date():
    """The configured date wins; the run's created_at is not implicit here.

    || La fecha configurada gana; el created_at de la corrida no es implícito.
    """
    rows = [_row(DEFFECDATE="2024-03-01", DNULLDATE="2024-04-01", NCODE="march")]
    in_march = apply_validity(
        rows, mechanism="period", as_of=date(2024, 3, 15), apply_status=False
    )
    in_june = apply_validity(
        rows, mechanism="period", as_of=date(2024, 6, 1), apply_status=False
    )

    assert len(in_march.kept) == 1
    assert in_june.kept == []


def test_both_mechanisms_report_discrepancy_and_keep_intersection():
    rows = [
        _row(SSTATREGT="1", DEFFECDATE="2020-01-01", DNULLDATE=None, NCODE="both_ok"),
        _row(SSTATREGT="3", DEFFECDATE="2020-01-01", DNULLDATE=None, NCODE="status_out"),
        _row(SSTATREGT="1", DEFFECDATE="2026-12-01", DNULLDATE=None, NCODE="period_out"),
    ]
    counts = apply_validity(
        rows, mechanism="both", as_of=date(2026, 1, 1), apply_status=True
    )

    assert [row.values["NCODE"] for row in counts.kept] == ["both_ok"]
    assert counts.validity_discrepancy == 2


def test_unparsed_date_is_counted_and_does_not_break():
    rows = [
        _row(DEFFECDATE="no-es-fecha", DNULLDATE=None, NCODE="bad"),
        _row(DEFFECDATE="2020-01-01", DNULLDATE=None, NCODE="ok"),
    ]
    counts = apply_validity(
        rows, mechanism="period", as_of=date(2026, 1, 1), apply_status=False
    )

    assert [row.values["NCODE"] for row in counts.kept] == ["ok"]
    assert counts.date_unparsed == 1


def test_none_mechanism_does_not_filter():
    rows = [_row(SSTATREGT="3", NCODE="kept_anyway")]
    counts = apply_validity(
        rows, mechanism="none", as_of=date(2026, 1, 1), apply_status=True
    )

    assert len(counts.kept) == 1


def test_status_four_normalizes_to_three():
    code, from_four = normalize_status("4")
    assert code == "3"
    assert from_four is True


def test_parse_row_date_accepts_common_shapes():
    assert parse_row_date("2026-09-09") == date(2026, 9, 9)
    assert parse_row_date("09/09/2026") == date(2026, 9, 9)
    assert parse_row_date("garbage") is None


def test_table26_catalog_is_detected_and_others_are_not():
    assert status_catalog_is_table26("Estado del registro. Valores posibles según tabla 26")
    assert status_catalog_is_table26("see TABLE26") is True
    assert status_catalog_is_table26("Valores posibles según tabla 1541") is False
    assert status_catalog_is_table26("Estado del registro.") is False
    assert status_catalog_is_table26(None) is False


def test_a_foreign_catalog_blocks_the_status_filter():
    """Generic 'Estado del registro.' still uses the TABLE26 assumption.

    Only a declared other catalog (or an inline 0/1) opts out. Measured
    2026-09-11 on run 20260909_214921: 4 TABLE<n> remit elsewhere, 573
    are generic, 137 remit to table 26.

    || Un «Estado del registro.» genérico sigue usando el supuesto TABLE26.
    Solo un catálogo declarado distinto se sale.
    """
    assert status_catalog_is_foreign("Valores posibles según la tabla 1520") is True
    assert status_catalog_is_foreign("según la tabla 535") is True
    assert status_catalog_is_foreign("según la tabla TABLE9150") is True
    assert status_catalog_is_foreign("1 ACTIVO - 0 DESACTIVO") is True
    assert status_catalog_is_foreign("Estado del registro.") is False
    assert status_catalog_is_foreign("Valores posibles según tabla 26") is False
    assert status_catalog_is_foreign(None) is False
    assert apply_status_filter("Estado del registro.") is True
    assert apply_status_filter("según la tabla 1541") is False

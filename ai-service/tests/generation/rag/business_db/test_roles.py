"""One test per declared rule, plus the order and the honest `unknown`.

|| Un test por regla declarada, más el orden y el `unknown` honesto.
"""

from __future__ import annotations

import pytest

from app.generation.rag.business_db.roles import ROLES, classify_role, routine_kind


class TestRoutineKind:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("INSVALCA014DB02", "validation"),
            ("INSPOSTCA014", "post"),
            ("INSPRECA048", "pre"),
            ("INSEXECUTECA048", "execute"),
            ("INSCOPYCA014", "copy"),
            ("REACA014", "read"),
            ("INSCA014PKG", "write"),
            ("UPDCLIENTBC003_K", "unknown"),
        ],
    )
    def test_prefix(self, name: str, expected: str) -> None:
        assert routine_kind(name) == expected

    def test_specific_prefix_beats_generic(self) -> None:
        # INSVAL and INSPOST both start with INS; the ordered rules decide.
        # || INSVAL e INSPOST empiezan con INS; deciden las reglas ordenadas.
        assert routine_kind("INSVALCA014") == "validation"
        assert routine_kind("INSPOSTCA014") == "post"


class TestDestinationSignals:
    def test_generic_table_by_name(self) -> None:
        role, reason = classify_role(
            table_name="TABLE221", description=None, via_routines=["INSPOSTCA025"]
        )
        assert role == "reference"
        assert "TABLE<n>" in reason

    def test_fixed_content_by_description(self) -> None:
        role, _ = classify_role(
            table_name="SOMETHING",
            description="Tabla de transacciones de poliza\n(Contenido fijo)",
            via_routines=["INSPOSTCA025"],
        )
        assert role == "reference"

    def test_message_tables(self) -> None:
        for name in ("MESSAGE", "WIN_MESSAG"):
            role, _ = classify_role(
                table_name=name, description=None, via_routines=["INSPRECA048"]
            )
            assert role == "message"

    def test_history_by_suffix(self) -> None:
        role, _ = classify_role(
            table_name="POLICY_HIS", description=None, via_routines=["REACA001"]
        )
        assert role == "historical"

    def test_history_by_description(self) -> None:
        role, _ = classify_role(
            table_name="EXPIRATION",
            description="Historia de los vencimientos",
            via_routines=["REACA001"],
        )
        assert role == "historical"


class TestPathSignals:
    def test_validation_only(self) -> None:
        role, reason = classify_role(
            table_name="NOPAYROLL",
            description="Novedades de nomina",
            via_routines=["INSVALCA014DB02", "INSVALCA014DB03"],
        )
        assert role == "validation"
        assert "INSVAL" in reason

    def test_validation_plus_write_is_not_validation(self) -> None:
        role, _ = classify_role(
            table_name="NOPAYROLL",
            description=None,
            via_routines=["INSVALCA014DB02", "INSPOSTCA014"],
        )
        assert role == "unknown"


class TestOrderAndUnknown:
    def test_destination_beats_path(self) -> None:
        # Reached only by validation routines, but it is a TABLE<n>: what the
        # table IS outranks how it was reached.
        # || Alcanzada solo por validación, pero es TABLE<n>: gana el destino.
        role, _ = classify_role(
            table_name="TABLE221", description=None, via_routines=["INSVALCA025ALL"]
        )
        assert role == "reference"

    def test_unknown_carries_its_reason(self) -> None:
        role, reason = classify_role(
            table_name="COVER",
            description="Coberturas de la poliza",
            via_routines=["INSPOSTCA014", "REACA014"],
        )
        assert role == "unknown"
        assert "ninguna regla declarada aplica" in reason
        assert "post" in reason and "read" in reason

    def test_unknown_with_no_routines_says_so(self) -> None:
        _, reason = classify_role(table_name="COVER", description=None, via_routines=[])
        assert "ninguna rutina" in reason

    def test_there_is_no_core_role(self) -> None:
        # Not an omission: measured against the annotated set, no declared
        # signal isolates it and the proposed fan-in rule runs backwards.
        # || No es un olvido: ninguna señal declarada lo aísla.
        assert "core" not in ROLES
